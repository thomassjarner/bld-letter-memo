import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
import flet as ft
from data.cloud_merge import Difference
from data.cloud_sync import CloudSync
from scripts.cloud_build import endpoint, prepare, stage
from test_cloud_sync import Cloud, device
from test_navigation import click_nav, mount, no_client_mount, walk


def test_guest_only_build_preserves_settings_and_signed_in_panel_needs_consent():
    page,repo=mount();settings=click_nav(page,"Settings")
    assert not any(getattr(x,"url",None) for x in walk(settings.account.control))
    async def run():
        service=Cloud();sync,state,_=await device(service);a=settings.account;a.cloud=sync
        sync.changed=a.render;a.render()
        button=next(x for x in walk(a.control) if getattr(x,"content",None)=="Enable sync")
        assert service.document is None
        await button.on_click(None);assert service.document is not None
        assert any(getattr(x,"content",None)=="Sync now" for x in walk(a.control))
        # Ordinary sign-out retains local data and re-exposes the WCA link.
        await next(x for x in walk(a.control) if getattr(x,"content",None)=="Sign out").on_click(None)
        button=next(c for c in walk(a.control) if getattr(c,"content",None)=="Sign in with WCA")
        assert button.url.url==sync.client.login_url and button.url.target==ft.UrlTarget.SELF
    asyncio.run(run())


def test_conflict_ui_shows_both_words_and_buttons_resolve_the_displayed_choice():
    page,_=mount();settings=click_nav(page,"Settings")
    async def run():
        server=Cloud();mac,m,_=await device(server);phone,p,_=await device(server)
        await mac.enable();await phone.enable()
        a=settings.account;a.cloud=phone;phone.changed=a.render
        m.set_word("AB","apple");p.set_word("AB","album");await mac.sync();await phone.sync()
        words=[x.value for x in walk(a.control) if isinstance(x,ft.Text)]
        assert "album" in words and "apple" in words
        await next(c for c in walk(a.control) if getattr(c,"content",None)=="Keep cloud").on_click(None)
        assert p.get_word("AB")=="apple" and not phone.differences
    asyncio.run(run())


def test_staged_pages_artifact_never_copies_private_worker_files(tmp_path):
    src=Path(__file__).resolve().parents[1]
    out=tmp_path/"stage";dist=tmp_path/"dist";dist.mkdir()
    stage(out,"https://sync.example/",src);prepare(dist,"https://sync.example/",src)
    assert not (out/"cloud").exists() and not (out/"web_cloud").exists()
    assert (out/"data/cloud_endpoint.py").read_text().endswith("'https://sync.example'\n")
    assert 'https://sync.example' in (dist/"cloud-endpoint.mjs").read_text()
    assert (dist/"account.html").is_file() and (out/"core/blddb_corner_catalog.json").is_file()
    assert "WCA_CLIENT_SECRET" not in "".join(p.read_text() for p in dist.iterdir())
    prepare(dist,"",src);assert 'API = ""' in (dist/"cloud-endpoint.mjs").read_text()


@pytest.mark.parametrize("value",["http://sync.example","https://user:secret@sync.example","https://sync.example/?secret=foo","https://sync.example/auth/callback"])
def test_config_accepts_only_the_public_origin(value):
    with pytest.raises(ValueError):endpoint(value)


def test_return_from_wca_opens_settings_and_refocusing_the_tab_checks_cloud_updates():
    from types import SimpleNamespace
    from flet.controls.base_control import BaseControl
    from test_navigation import PageHarness
    from ui import app
    async def run():
        server=Cloud();device_sync,_s,_p=await device(server)
        client=device_sync.client;client.returning=True
        page=PageHarness();tasks=[]
        page.run_task=lambda cb,*args:tasks.append(asyncio.create_task(cb(*args)))
        async def finish():
            while tasks:
                batch=list(tasks);tasks.clear();await asyncio.gather(*batch)
        with patch.object(app,"SYNC_URL","https://sync.example"),patch.object(app.BrowserCloud,"open",AsyncMock(return_value=client)),patch.object(app.SharedPreferencesAppDataRepository,"create",AsyncMock(return_value=device_sync.repo)),patch.object(BaseControl,"update",lambda self:None):
            await app.main(page);await finish()
            settings=page.root.controls[0].content
            assert settings.account.cloud.session["user"]["name"]=="Tester" and server.document is None
            await settings.account.cloud.enable()
            server.document["global_words"]={"AB":"album"};server.revision+=1
            page.on_app_lifecycle_state_change(SimpleNamespace(state=ft.AppLifecycleState.RESUME))
            await finish()
            assert settings.state.get_word("AB")=="album"
    asyncio.run(run())
