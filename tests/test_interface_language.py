"""Exercise the live language picker, independent browser storage and cubing UI."""
import asyncio
from copy import deepcopy
from string import Formatter
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import flet as ft
import pytest

from core.messages import ENGLISH, SIMPLIFIED_CHINESE as ZH, in_language, join_text, message
from core.zh_cn import MESSAGES
from data.models import PracticeSolve
from test_navigation import PageHarness, click_nav, no_client_mount, text_values
from test_progressive_memo import letter_scheme
from test_workspace_preferences import Host, Preferences, Repository, reopen
from ui import app


def event(value):
    return SimpleNamespace(control=SimpleNamespace(value=value))


def test_switch_reopen_and_switch_back_without_changing_the_workspace():
    async def mounted(host, prefs):
        repo = await reopen(host, prefs)
        page = PageHarness()
        with patch.object(app.SharedPreferencesAppDataRepository, "create", AsyncMock(return_value=repo)):
            await app.main(page)
        return page, repo

    async def run():
        host, prefs = Host(), Preferences()
        en, repo = await mounted(host, prefs)
        settings = click_nav(en, "Settings")
        scheme = letter_scheme()
        scheme.name = "Home"  # Exactly matches an English navigation label.
        state = settings.state
        state.data.schemes = {scheme.name: scheme}
        state.data.active_scheme = scheme.name
        state.data.global_words = {"AB": "Settings"}
        state.data.practice_solves = [PracticeSolve(1200, "R U"), PracticeSolve(1400, "F2", dnf=True)]
        repo.save(state.data)
        await host.finish()
        saved = deepcopy(state.data.to_dict())
        snapshot = prefs.values[Repository.STORAGE_KEY]
        assert settings.language_picker.value == ENGLISH and "General" in text_values(settings)
        await settings.language_picker.on_select(event(ZH))
        assert en.root.controls[0].content is settings
        assert "常规" in text_values(settings)
        assert settings.dark_mode_switch.label == "深色模式"
        assert settings.language_picker.value == ZH
        assert [(o.key, o.text) for o in settings.language_picker.options] == [("en","English"),(ZH,"简体中文")]
        assert prefs.values[Repository.STORAGE_KEY] == snapshot and state.data.to_dict() == saved
        assert en.locale_configuration.current_locale.language_code == "zh"
        assert en.theme.font_family == en.dark_theme.font_family == "BLDMemoHans"

        reopened, second = await mounted(host, prefs)
        home = reopened.root.controls[0].content
        assert "设置编码方案" in text_values(home)
        timer = click_nav(reopened, "计时器")
        timer._select_activity_tab("stats")
        stats = timer.body_host.content
        assert [m.title.value for m in stats.metrics] == ["成功率","成功还原平均用时","成功还原用时中位数"]
        assert [m.value.value for m in stats.metrics] == ["50.0%", "12.00", "12.00"]
        assert stats.filter_picker.value == "Session 1"
        assert stats.filter_picker.options[0].text == "分组 1"
        library = click_nav(reopened, "方法库")
        library._set_mode("library")
        assert library.scheme_picker.value == "Home" and library.scheme_picker.options[0].key == "Home"
        assert library.case_converter.commutator.label == "交换子"
        assert library.name_field.value == "我的公式"
        source = library.case_converter.final_alg.value
        assert source and all(c.isascii() for c in source)
        library._set_mode("explorer")
        library.playground_name.value = "Settings"
        settings = click_nav(reopened, "设置")
        await settings.language_picker.on_select(event(ENGLISH))
        assert settings.dark_mode_switch.label == "Dark mode"
        library = click_nav(reopened, "Method Library")
        assert library.playground_name.value == "Settings"
        library._set_mode("library")
        assert library.case_converter.commutator.label == "Commutator"
        assert library.name_field.value == "My alg"
        assert library.case_converter.final_alg.value == source
        assert second.load().to_dict() == saved
        again, _ = await mounted(host, prefs)
        assert "Set up your letter scheme" in text_values(again.root.controls[0].content)

    asyncio.run(run())


def test_unsupported_or_unreadable_language_and_failed_write_leave_english_selected():
    async def run():
        class FailingPrefs(Preferences):
            async def get(self, key):
                if key == Repository.LANGUAGE_KEY: raise OSError("unavailable")
                return await super().get(key)
        host = Host()
        for raw in (None, "", "fr", "zh-TW", ["zh-CN"]):
            prefs = Preferences({Repository.LANGUAGE_KEY:raw})
            assert await (await reopen(host, prefs)).load_language() == ENGLISH
        prefs = FailingPrefs(); prefs.fail_key = Repository.LANGUAGE_KEY
        repo = await reopen(host,prefs)
        assert await repo.load_language() == ENGLISH
        page = PageHarness()
        with patch.object(app.SharedPreferencesAppDataRepository,"create",AsyncMock(return_value=repo)):
            await app.main(page)
        settings = click_nav(page, "Settings")
        await settings.language_picker.on_select(event(ZH))
        assert settings.language_picker.value == ENGLISH and "Could not save" in settings.language_hint.value
        assert page.locale_configuration.current_locale.language_code == "en"
    asyncio.run(run())


def test_user_arguments_keep_their_spelling_through_nested_templates_and_errors():
    alg = "[R U: [D, R' Fw2 R]]"
    mixed = join_text(" · ", [message("Commutator"), alg, "Home", "晓明", "AB", "UFR"])
    both = message("Back to {0}", in_language(mixed, ZH))
    assert str(in_language(both, ZH)) == "返回交换子 · "+alg+" · Home · 晓明 · AB · UFR"
    assert in_language(in_language(both, ZH), ENGLISH) == "Back to Commutator · "+alg+" · Home · 晓明 · AB · UFR"
    assert in_language(ValueError(message("Unsupported move: {0}", "Home")), ZH) == "不支持的转动：Home"
    assert in_language("Learned", ZH) == "Learned"


def test_translated_format_fields_preserve_the_data_and_number_formats():
    def fields(s):
        return sorted((name, spec, conversion) for _,name,spec,conversion in Formatter().parse(s) if name is not None)
    for english, chinese in MESSAGES.items():
        assert fields(english) == fields(chinese), english
