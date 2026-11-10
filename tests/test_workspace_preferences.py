"""Reopen real browser repositories with rollback copies and in-flight saves."""
import asyncio
from copy import deepcopy
import json
from unittest.mock import AsyncMock, patch

import flet as ft
import pytest
from data.color_themes import LIGHT_THEMES
from data.models import AppData, LetterScheme, PracticeSolve, CURRENT_VERSION
from data.shared_preferences_repository import SharedPreferencesAppDataRepository as Repository
from test_navigation import PageHarness, click_nav, no_client_mount
from ui import app
from ui.state import AppState


class Preferences:
    def __init__(self, values=None):
        self.values=values or {};self.writes=[];self.fail_key=None
    async def get(self,key):return self.values.get(key)
    async def set(self,key,value):
        self.writes.append(key)
        if key==self.fail_key:raise OSError('Test write interruption')
        self.values[key]=value


class Host:
    def __init__(self):self.tasks=[]
    def run_task(self,callback,*args):self.tasks.append(asyncio.create_task(callback(*args)))
    async def finish(self):
        while self.tasks:
            tasks,self.tasks=self.tasks,[]
            await asyncio.gather(*tasks)


def data_with_schemes():
    data=AppData(schemes={name:LetterScheme(name=name) for name in ('A','B')},active_scheme='A')
    data.global_words={'AB':'Apple'};data.practice_solves=[PracticeSolve(2630,'R U')]
    return data


async def reopen(host,prefs):
    with patch('data.shared_preferences_repository.ft.SharedPreferences',return_value=prefs):
        return await Repository.create(host)


def test_latest_light_mode_and_active_scheme_win_over_a_legacy_dark_rollback():
    async def run():
        current=data_with_schemes();current.active_scheme='B';current.light_theme='rose'
        old=deepcopy(current);old.active_scheme='A';old.dark_mode=True;old.light_theme='warm_sand'
        prefs=Preferences({Repository.STORAGE_KEY:json.dumps(current.to_dict()),
            Repository.SHADOW_KEY:json.dumps(current.to_dict()),Repository.ROLLBACK_KEY:json.dumps(old.to_dict())})
        restored=(await reopen(Host(),prefs)).load()
        assert restored.to_dict()==current.to_dict()
        assert restored.version==CURRENT_VERSION==18
    asyncio.run(run())


def test_scheme_mode_and_palette_survive_rapid_changes_and_a_full_app_restart():
    async def run():
        host,prefs=Host(),Preferences();repo=Repository(host,prefs,data_with_schemes(),None)
        state=AppState(repo);statuses=[];state.on_save_status(statuses.append)
        state.switch_scheme('B');state.set_dark_mode(True);state.set_light_theme('warm_sand')
        state.set_dark_mode(False);state.set_light_theme('cobalt')
        assert statuses[-1]=='Saving…' and 'Saved' not in statuses
        await host.finish();assert statuses[-1]=='Saved'
        expected=deepcopy(state.data.to_dict())
        new_repo=await reopen(Host(),prefs);assert new_repo.load().to_dict()==expected
        page=PageHarness()
        with patch.object(app.SharedPreferencesAppDataRepository,'create',AsyncMock(return_value=new_repo)):
            await app.main(page)
        assert page.theme_mode==ft.ThemeMode.LIGHT
        assert page.theme.color_scheme.primary==LIGHT_THEMES['cobalt'].colors['primary']
        assert click_nav(page,'Letter Schemes').state.active_scheme.name=='B'
        assert prefs.writes[0]==Repository.PREFERENCES_KEY
        assert prefs.values[Repository.STORAGE_KEY]==prefs.values[Repository.SHADOW_KEY]
    asyncio.run(run())


def test_preferences_are_written_before_large_backups_and_survive_an_interrupted_full_save():
    async def run():
        initial=data_with_schemes();payload=json.dumps(initial.to_dict())
        prefs=Preferences({Repository.STORAGE_KEY:payload,Repository.SHADOW_KEY:payload})
        host=Host();state=AppState(Repository(host,prefs,initial,payload));statuses=[];state.on_save_status(statuses.append)
        prefs.fail_key=Repository.ROLLBACK_KEY
        state.switch_scheme('B');state.set_dark_mode(True);state.set_light_theme('rose')
        await host.finish()
        assert statuses[-1].startswith('Save failed')
        restored=await reopen(Host(),prefs)
        assert restored.load().active_scheme=='B' and restored.load().dark_mode
        assert restored.load().light_theme=='rose'
        assert restored.load().global_words=={'AB':'Apple'}
        prefs.fail_key=None;state.set_dark_mode(False);await host.finish()
        assert statuses[-1]=='Saved'
        assert (await reopen(Host(),prefs)).load().to_dict()==state.data.to_dict()
    asyncio.run(run())


def test_recovering_richer_data_keeps_the_latest_workspace_preferences():
    async def run():
        rich=data_with_schemes();rich.dark_mode=True
        prefs=Preferences({Repository.STORAGE_KEY:json.dumps(AppData().to_dict()),
            Repository.ROLLBACK_KEY:json.dumps(rich.to_dict()),Repository.PREFERENCES_KEY:json.dumps(
                {'active_scheme':'B','dark_mode':False,'light_theme':'lavender'})})
        restored=(await reopen(Host(),prefs)).load()
        assert set(restored.schemes)=={'A','B'} and restored.active_scheme=='B'
        assert not restored.dark_mode and restored.light_theme=='lavender'
        assert restored.global_words==rich.global_words and restored.practice_solves==rich.practice_solves
    asyncio.run(run())


@pytest.mark.parametrize('raw',['{',json.dumps([]),json.dumps({'active_scheme':'deleted','dark_mode':'false',
                                                    'light_theme':['rose']})])
def test_invalid_or_deleted_workspace_preferences_do_not_replace_valid_profile_data(raw):
    async def run():
        data=data_with_schemes();data.active_scheme='B';data.light_theme='cobalt'
        prefs=Preferences({Repository.STORAGE_KEY:json.dumps(data.to_dict()),Repository.PREFERENCES_KEY:raw})
        assert (await reopen(Host(),prefs)).load().to_dict()==data.to_dict()
    asyncio.run(run())
