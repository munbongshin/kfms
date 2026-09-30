"""Messages in the language the screen is set to.

The screens send `Accept-Language: ko` or `en` with every request. The server
writes its messages in Korean; for English this module translates them on the
way out, so the many places that raise or return a message do not each need to
know about languages.

Two kinds of catalog entry (see i18n_catalog.py):

* exact text — "사용자를 찾을 수 없습니다"
* a template with {placeholders} for the parts that vary —
  "'{name}' 이름의 연결이 이미 있습니다". The captured parts are translated too
  (a weekday, a label), and left alone when they are data.

Only messages are translated: JSON values under a fixed set of keys, and never
inside the parts of a response that hold data (query results, schema, column
names), so a value from the database cannot be changed by accident.
"""
import json
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from app.i18n_catalog import EXACT, TEMPLATES

# JSON keys whose string values are messages.
MESSAGE_KEYS = {
    "detail", "message", "error", "caveat", "summary", "label", "hint", "text", "rule",
    "reason", "last_error", "warnings", "note", "description",
}
# Parts of a response that hold data: never translated.
DATA_KEYS = {"results", "rows", "last_results", "transactions", "schema", "columns", "tables", "selected"}


def language_of(header: Optional[str]) -> str:
    """'en' when the Accept-Language header asks for English, else 'ko'."""
    return "en" if (header or "").strip().lower().startswith("en") else "ko"


_UNITS = ("원", "건", "분", "시")


@lru_cache(maxsize=1)
def _patterns() -> List[Tuple["re.Pattern[str]", str]]:
    compiled = []
    for ko, en in TEMPLATES.items():
        parts = re.split(r"(\{\w+\})", ko)
        regex = ""
        for index, part in enumerate(parts):
            if not re.fullmatch(r"\{\w+\}", part):
                regex += re.escape(part)
                continue
            # A blank right before a unit (원, 건, 분, 시) is a number; a merchant
            # called "화   원" must not be read as an amount.
            following = parts[index + 1][:1] if index + 1 < len(parts) else ""
            what = r"[\d,.\-]+" if following in _UNITS else ".+?"
            regex += f"(?P<{part[1:-1]}>{what})"
        compiled.append((re.compile(f"^{regex}$", re.S), en))
    # The most specific template first: the one with the most fixed text.
    compiled.sort(key=lambda item: -len(re.sub(r"\(\?P<\w+>[^)]*\)", "", item[0].pattern)))
    return compiled


def translate(text: str, lang: str) -> str:
    """`text` in `lang`; unchanged when it is Korean already or is not a known message."""
    if lang != "en" or not text or not re.search("[가-힣]", text):
        return text
    if text in EXACT:
        return EXACT[text]

    for pattern, en in _patterns():
        match = pattern.match(text)
        if match:
            parts = {name: translate(value, lang) for name, value in match.groupdict().items()}
            return en.format(**parts)

    # A message made of several parts (a list of changes, one note per year).
    for separator in (" / ", " · ", ", "):
        if separator in text:
            pieces = text.split(separator)
            translated = [translate(piece, lang) for piece in pieces]
            if translated != pieces:
                return separator.join(translated)
    return text


def translate_json(value: Any, lang: str, key: Optional[str] = None) -> Any:
    """`value` with its messages translated; data is passed through untouched."""
    if lang != "en":
        return value
    if isinstance(value, dict):
        return {k: (v if k in DATA_KEYS else translate_json(v, lang, k)) for k, v in value.items()}
    if isinstance(value, list):
        return [translate_json(v, lang, key) for v in value]
    if isinstance(value, str) and key in MESSAGE_KEYS:
        return translate(value, lang)
    return value


def translate_body(body: bytes, lang: str) -> bytes:
    """A JSON response body with its messages translated; anything else is returned as it came."""
    if lang != "en":
        return body
    try:
        payload = json.loads(body)
    except ValueError:
        return body
    return json.dumps(translate_json(payload, lang), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
