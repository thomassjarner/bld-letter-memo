from copy import deepcopy
import asyncio
import json

import pytest
from data.cloud_client import CloudError
from data.cloud_merge import Difference, identify, merge, validate
from data.cloud_sync import CloudSync
from data.models import AppData, LetterScheme, PracticeSolve
from data.shared_preferences_repository import SharedPreferencesAppDataRepository as Repo
from test_workspace_preferences import Host, Preferences, reopen
from ui.state import AppState


class Cloud:
    def __init__(self):
        self.document=None; self.revision=0; self.before_write=None


class Client:
    login_url="https://example.invalid/trainer/account.html"
    returning=False
    def __init__(self,cloud):
        self.cloud=cloud;self.info={"tag":"device","user":{"id":42,"name":"Tester","wca_id":""},"enabled":False}
        self.anchor=None;self.offline=False;self.calls=[]
    async def call(self,op,**args):
        self.calls.append(op)
        if op=="info": return deepcopy(self.info)
        assert args["tag"]=="device"
        if op=="base":return deepcopy(self.anchor)
        if op=="forget":self.info=self.anchor=None;return
        if op=="commit":
            self.info["enabled"]=True;self.anchor={k:deepcopy(args[k]) for k in ("revision","workspace")};return
        if self.offline:raise CloudError("Offline.")
        if op=="logout":return
        cloud=self.cloud
        if op=="read":
            if args.get("since") and args["since"]==cloud.revision:
                return {"revision":cloud.revision,"unchanged":True}
            return {"revision":cloud.revision,"workspace":deepcopy(cloud.document)}
        assert op=="write"
        if cloud.before_write:
            action,cloud.before_write=cloud.before_write,None;action()
        if args["body"]["revision"]!=cloud.revision:raise CloudError("Stale version",409)
        cloud.revision+=1;cloud.document=deepcopy(args["body"]["workspace"])
        return {"revision":cloud.revision}


async def device(cloud,data=None,prefs=None,client=None):
    host=Host();prefs=prefs or Preferences()
    if data is not None: prefs.values[Repo.STORAGE_KEY]=json.dumps(data.to_dict())
    repo=await reopen(host,prefs);state=AppState(repo)
    c=CloudSync(state,repo,client or Client(cloud),lambda _:None)
    await c.initialize()
    return c,state,prefs


def test_two_devices_first_consent_restore_merge_conflict_and_reopen():
    async def run():
        cloud=Cloud();original=AppData();sc=LetterScheme("Speffz")
        sc.corners.cycle_break_priority=["UBL","UBR"];sc.corners.cycle_break_stickers={"UBL":"LUB"}
        original.active_scheme="Speffz";original.schemes={"Speffz":sc}
        original.global_words={"IR":"iris"};original.dark_mode=True
        mac,m,prefs=await device(cloud,original)
        assert mac.client.calls==["info"] and cloud.document is None
        await mac.enable()
        assert mac.session["enabled"] and cloud.document["schemes"]==original.to_dict()["schemes"]
        phone,p,_=await device(cloud)
        assert not p.data.schemes and phone.client.calls==["info"]
        await phone.enable()
        assert p.data.to_dict()==m.data.to_dict() and p.data.dark_mode
        m.add_practice_solve(2630,"R U"); m.set_word("IR","iron")
        p.add_practice_solve(2630,"R U"); p.set_word("IR","ice rink");p.set_pair_alias("AX","AØ")
        await mac.sync();await phone.sync()
        assert [d.label for d in phone.differences]==["Letter pair · IR"]
        assert Difference.describe(phone.differences[0].cloud)=="iron"
        assert p.get_word("IR")=="ice rink" and cloud.document["global_words"]["IR"]=="iron"
        await phone.decide("device");await mac.sync()
        assert m.get_word("IR")=="ice rink" and m.data.pair_aliases=={"AX":"AØ"}
        assert len({s.id for s in m.data.practice_solves})==2 and m.data.to_dict()==p.data.to_dict()
        again,state,_=await device(cloud,prefs=prefs,client=mac.client)
        assert again.consent and state.data.to_dict()==m.data.to_dict()
        assert not set(state.data.to_dict()) & {"token","tag","user","cloud"}
    asyncio.run(run())


def test_review_is_bound_to_values_and_changed_remote_choice_is_reshown():
    async def run():
        cloud=Cloud();mac,m,_=await device(cloud);phone,p,_=await device(cloud)
        await mac.enable();await phone.enable()
        m.set_word("IR","iron");p.set_word("IR","iris")
        await mac.sync();await phone.sync()
        assert len(phone.differences)==1
        m.set_word("IR","ice rink");await mac.sync()
        await phone.decide("cloud")
        assert len(phone.differences)==1 and Difference.describe(phone.differences[0].cloud)=="ice rink"
        await phone.decide("cloud")
        assert p.data.global_words=={"IR":"ice rink"}
    asyncio.run(run())


def test_remote_delete_stays_deleted_after_local_restart_with_a_richer_rollback():
    async def run():
        cloud=Cloud();mac,m,_=await device(cloud)
        m.create_scheme("Old");m.set_word("AB","apple");await mac.enable()
        phone,p,prefs=await device(cloud);await phone.enable()
        m.set_word("AB","");await mac.sync();await phone.sync()
        assert p.get_word("AB")=="" and "apple" in prefs.values[Repo.ROLLBACK_KEY]
        again,state,_=await device(cloud,prefs=prefs,client=phone.client)
        assert state.get_word("AB")=="" and not again.differences
    asyncio.run(run())


def test_local_failure_offline_and_stale_write_keep_new_work():
    async def run():
        c=Cloud();s,model,prefs=await device(c);await s.enable()
        prefs.fail_key=Repo.STORAGE_KEY;model.set_word("FB","football");await s.sync()
        assert c.document["global_words"]=={} and "cloud sync is paused" in s.message
        prefs.fail_key=None;model.set_word("CD","disc");s.client.offline=True
        await s.sync();assert model.get_word("FB")=="football" and c.document["global_words"]=={}
        s.client.offline=False
        def concurrent():
            c.document["global_words"]["PQ"]="penguin";c.revision+=1
        c.before_write=concurrent;await s.sync()
        assert model.data.global_words==c.document["global_words"]=={"FB":"football","CD":"disc","PQ":"penguin"}
        def edit_during_request(): model.set_word("AB","anchor")
        model.set_word("IR","iris");c.before_write=edit_during_request;await s.sync()
        assert c.document["global_words"]["AB"]=="anchor"
    asyncio.run(run())


def test_active_training_delays_external_changes_and_offline_logout_keeps_guest_work():
    async def run():
        c=Cloud();mac,m,_=await device(c);await mac.enable()
        phone,p,_=await device(c);await phone.enable()
        m.create_scheme("New");await mac.sync()
        phone.safe=lambda:False
        await phone.sync()
        assert p.active_scheme is None and "Open Settings" in phone.message
        phone.safe=lambda:True;await phone.sync()
        assert p.active_scheme.name=="New"
        phone.client.offline=True;await phone.disconnect()
        assert not phone.session and not phone.consent and p.active_scheme.name=="New"
        p.set_word("KL","kite");await phone.sync()
        assert "KL" not in c.document["global_words"]
    asyncio.run(run())


def test_legacy_duplicate_solves_match_without_inventing_times_or_losing_a_penalty():
    base=AppData();base.practice_solves=[PracticeSolve(100,"R U"),PracticeSolve(100,"R U")]
    backup=base.to_dict();local=deepcopy(backup);remote=identify(backup)
    local["practice_sessions"]["Session 1"][1]["plus2"]=True
    merged,diffs=merge(backup,local,remote)
    solves=merged["practice_sessions"]["Session 1"]
    assert not diffs and len(solves)==2 and len({r["id"] for r in solves})==2
    assert [r["plus2"] for r in solves]==[False,True] and all("recorded_at" not in r for r in solves)
    assert identify(merged)==merged and "id" not in backup["practice_sessions"]["Session 1"][0]


def test_word_and_its_rating_are_one_decision_and_delete_vs_edit_is_explicit():
    a=AppData();a.global_words={"AB":"apple"};a.pair_ratings={"AB":3};a.pair_rating_versions={"AB":1}
    b=a.to_dict();l=deepcopy(b);r=deepcopy(b)
    for k in ("global_words","pair_ratings","pair_rating_versions"): l[k].clear()
    r["pair_ratings"]["AB"]=4
    _,ds=merge(b,l,r);d,=ds
    assert d.describe(d.device)=="Deleted" and d.describe(d.cloud)=="apple · rating 4/5"
    m,ds=merge(b,l,r,{d.path:(d.device,d.cloud,"cloud")})
    assert m==r and not ds


def test_alg_lists_merge_by_id_and_future_or_duplicate_cloud_data_stop():
    from data.models import PlaygroundAlgorithm,CornerCaseRecord,CaseAlgorithm
    b=AppData().to_dict()
    l=AppData(playground_algorithms=[PlaygroundAlgorithm("one","One","R U")]);r=AppData(playground_algorithms=[PlaygroundAlgorithm("two","Two","R L")])
    l.corner_case_library["x"]=CornerCaseRecord(algorithms=[CaseAlgorithm("a","A","R")])
    r.corner_case_library["x"]=CornerCaseRecord(algorithms=[CaseAlgorithm("b","B","U")])
    merged,ds=merge(b,l.to_dict(),r.to_dict());assert not ds
    assert len(merged["playground_algorithms"])==len(merged["corner_case_library"]["x"]["algorithms"])==2
    with pytest.raises(ValueError):validate({**b,"version":19})
    duplicate=deepcopy(b);entry=PracticeSolve(10,"R",id="same").to_dict()
    duplicate["practice_sessions"]["Session 1"]=[entry,entry]
    with pytest.raises(ValueError):validate(duplicate)


def test_a_different_wca_account_cannot_upload_prior_users_local_workspace():
    async def run():
        c=Cloud();first,model,prefs=await device(c)
        model.set_word("IR","my own image")
        await first.enable()
        await first.disconnect()
        other=Client(Cloud());other.info["user"]["id"]=99
        second,local,_=await device(other.cloud,prefs=prefs,client=other)
        assert second.blocked and not second.consent
        await second.enable();await second.sync()
        assert other.calls==["info"] and other.cloud.document is None and local.get_word("IR")=="my own image"
    asyncio.run(run())
