"""Authored UI copy. Keep the English source and its opaque arguments together.

The cube engine, option keys and saved data always use their canonical values.
Only the presentation layer requests a language. No lookup runs on user input.
"""
from functools import lru_cache

ENGLISH, SIMPLIFIED_CHINESE = "en", "zh-CN"


def normalize_language(code):
    return SIMPLIFIED_CHINESE if code == SIMPLIFIED_CHINESE else ENGLISH


@lru_cache(maxsize=1)
def _chinese():
    from core.zh_cn import MESSAGES
    return MESSAGES


class Message(str):
    """A string with enough provenance to switch languages without reloading."""

    def __new__(cls, value, kind, source, arguments, language=ENGLISH):
        result = super().__new__(cls, value)
        result.kind, result.source = kind, source
        result.arguments, result.language = arguments, language
        return result

    def __getnewargs__(self):
        return (str(self), self.kind, self.source, self.arguments, self.language)

    def __add__(self, other):
        return in_language(join_text("", (self, other)), self.language) if isinstance(other, str) else NotImplemented

    def __radd__(self, other):
        return in_language(join_text("", (other, self)), self.language) if isinstance(other, str) else NotImplemented

    def _case(self, method):
        return Message(getattr(str, method)(self), "case", method, (self,), self.language)

    def upper(self): return self._case("upper")
    def lower(self): return self._case("lower")
    def title(self): return self._case("title")
    def capitalize(self): return self._case("capitalize")


@lru_cache(maxsize=1536)
def _literal(source):
    return Message(source, "format", source, ())


def message(source, *arguments):
    """Mark a site-authored English message; never pass a user's name or text as source."""
    if not arguments:
        return _literal(source)
    canonical = tuple(in_language(arg, ENGLISH) for arg in arguments)
    value = source.format(*canonical) if arguments else source
    return Message(value, "format", source, arguments)


def compose(source, *arguments):
    """A language-neutral template (e.g. two labels separated by a middle dot)."""
    if any(isinstance(arg, (Message, BaseException)) for arg in arguments):
        return message(source, *arguments)
    return source.format(*arguments)


def join_text(separator, parts):
    parts = tuple(parts)
    if not any(isinstance(p, Message) for p in parts):
        return separator.join(parts)
    value = separator.join(in_language(part, ENGLISH) for part in parts)
    return Message(value, "join", separator, parts)


def error_message(error):
    if isinstance(error, BaseException) and len(error.args) == 1 and isinstance(error.args[0], Message):
        return error.args[0]
    return str(error)


def in_language(value, language):
    if isinstance(value, BaseException):
        value = error_message(value)
    if not isinstance(value, Message) or value.language == language:
        return value
    args = tuple(in_language(arg, language) for arg in value.arguments)
    if value.kind == "join":
        rendered = value.source.join(args)
    elif value.kind == "case":
        rendered = getattr(str, value.source)(args[0]) if language == ENGLISH else str(args[0])
    else:
        source = _chinese().get(value.source, value.source) if language == SIMPLIFIED_CHINESE else value.source
        rendered = source.format(*args) if args else source
    return Message(rendered, value.kind, value.source, value.arguments, language)
