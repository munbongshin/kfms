"""Every message the server writes in Korean has an English translation.

The code is scanned for Korean strings and f-strings; each must be translated by
the catalog or be on the short list of things that are not messages (patterns,
prompts, names of columns and terms that are data).
"""
import ast
import os
import re

from app.i18n import translate

APP = os.path.join(os.path.dirname(__file__), "..", "app")
HANGUL = re.compile("[가-힣]")

# Not messages: regular expressions, header aliases accepted on import, the LLM
# prompt, the names shown for computed columns and merchant categories (data),
# and text compared against rather than shown.
NOT_MESSAGES = {
    "^[A-Za-z0-9_.\\-가-힣]+$", "[ㄱ-ㆎ가-힣]",
    "컬럼", "영문명", "영문컬럼명", "한글컬럼명", "한글", "표시명", "라벨", "테이블", "테이블명",
    "합계", "건수", "평균", "최대값", "최소값", "계산값",
    "이름 미지정", "컬럼 없음", "임시",
    # Fragments that are joined into a longer message; the whole is what the catalog translates.
    " — 서비스키를 확인하세요", " ({category} 기준 {v} 이상)", "그 시점의 값을 지금은 쓸 수 없습니다: ",
    # The pattern that finds Hangul in text to translate.
    "[가-힣]",
    # The units that mark the number before them (app/i18n.py).
    "원", "건", "분", "시",
    "상품권 전문판매", "볼 링 장", "영화관", "화   원", "기타회원제형태업소4", "자사카드발행백화점",
}
SKIPPED_FILES = {"db/models.py"}


def placeholder_name(node, used):
    if isinstance(node, ast.Name):
        base = node.id
    elif isinstance(node, ast.Attribute):
        base = node.attr
    else:
        base = "v"
    base = re.sub(r"\W", "_", base) or "v"
    name, k = base, 2
    while name in used:
        name, k = f"{base}{k}", k + 1
    used.add(name)
    return name


def messages():
    found = []
    for directory, _, files in os.walk(APP):
        if "__pycache__" in directory:
            continue
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(directory, name)
            rel = os.path.relpath(path, APP).replace("\\", "/")
            if rel in SKIPPED_FILES:
                continue
            tree = ast.parse(open(path, encoding="utf-8").read())
            docstrings, inside_fstring = set(), set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                    body = node.body
                    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant):
                        docstrings.add(id(body[0].value))
                if isinstance(node, ast.JoinedStr):
                    inside_fstring.update(id(v) for v in node.values)
            for node in ast.walk(tree):
                if isinstance(node, ast.JoinedStr):
                    used = set()
                    text = "".join(
                        str(v.value) if isinstance(v, ast.Constant) else "{" + placeholder_name(v.value, used) + "}"
                        for v in node.values
                    )
                    if HANGUL.search(text):
                        found.append((rel, text))
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if id(node) in docstrings or id(node) in inside_fstring:
                        continue
                    if HANGUL.search(node.value) and "RULES:" not in node.value:
                        found.append((rel, node.value))
    return found


def sample_of(template: str) -> str:
    """A message of this template with something in each blank (a digit fits an amount as well as a name)."""
    return re.sub(r"\{\w+\}", "1", template)


def test_every_message_in_the_code_has_an_english_translation():
    untranslated = sorted({
        f"{rel}: {text}"
        for rel, text in messages()
        if text not in NOT_MESSAGES and translate(sample_of(text), "en") == sample_of(text)
    })
    assert untranslated == []
