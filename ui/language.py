"""Per-page presentation language. Changing it leaves the live controls and editors intact."""
from contextvars import ContextVar
import flet as ft
from core.messages import ENGLISH, SIMPLIFIED_CHINESE, Message, in_language, message, normalize_language

# A fallback for standalone mounting (e.g. embedded/test hosts without a Flet
# session). Keep the page reference, not a stale initial language or a global locale.
_host = ContextVar("bld_language_host", default=None)


def current_language():
    try:
        page = ft.context.page
    except RuntimeError:
        page = _host.get()
    return getattr(page, "_bld_language", ENGLISH)


def configure_language(page, code):
    code = normalize_language(code)
    page._bld_language = code
    _host.set(page)
    if code == SIMPLIFIED_CHINESE and "BLDMemoHans" not in (getattr(page, "fonts", None) or {}):
        page.fonts = {**(getattr(page, "fonts", None) or {}), "BLDMemoHans": "fonts/bld-memo-hans.otf"}
    en, zh = ft.Locale("en", "US"), ft.Locale(language_code="zh", country_code="CN", script_code="Hans")
    page.locale_configuration = ft.LocaleConfiguration(supported_locales=[en, zh],
        current_locale=zh if code == SIMPLIFIED_CHINESE else en)


def present(value):
    return in_language(value, current_language()) if isinstance(value, Message) else value


def tr(source, *arguments):
    return present(message(source, *arguments))
