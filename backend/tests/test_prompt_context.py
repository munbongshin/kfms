"""What is added to a question before the LLM sees it.

Three things raise accuracy without touching the model: verified question/SQL
pairs the user bookmarked (few-shot examples), the business terms the question
uses ("고액" = 50만원 이상), and — when generated SQL fails — the database's own
error message so the model can fix it.
"""
from app.services.prompt_context import (
    build_context,
    pick_examples,
    pick_terms,
    retry_context,
)

BOOKMARKS = [
    {"question": "승인내역에서 가맹점별 승인금액 합계 상위 5건", "sql": "SELECT merchname FROM v_approval"},
    {"question": "카테고리별 총 매출을 보여줘", "sql": "SELECT product_category FROM retail_sales"},
    {"question": "가맹점별 주소를 보여줘", "sql": "SELECT merchname, merchaddr FROM v_approval"},
]


# --- examples -----------------------------------------------------------

def test_the_most_similar_bookmark_comes_first():
    picked = pick_examples("가맹점별 승인금액 합계 상위 10건", BOOKMARKS, k=2)
    assert picked[0]["question"].startswith("승인내역에서 가맹점별 승인금액")


def test_only_k_examples_are_returned():
    assert len(pick_examples("가맹점별 합계", BOOKMARKS, k=2)) == 2


def test_an_unrelated_question_gets_no_examples():
    # A wrong example misleads more than none helps.
    assert pick_examples("zzz qqq", BOOKMARKS, k=3) == []


def test_no_bookmarks_no_examples():
    assert pick_examples("가맹점별 합계", [], k=3) == []


def test_the_same_question_is_not_repeated():
    dup = BOOKMARKS + [dict(BOOKMARKS[0])]
    picked = pick_examples("승인내역에서 가맹점별 승인금액 합계 상위 5건", dup, k=3)
    assert len({p["question"] for p in picked}) == len(picked)


# --- terms --------------------------------------------------------------

TERMS = [
    {"term": "고액", "definition": "한 건 결제금액이 50만원 이상"},
    {"term": "심야", "definition": "23시부터 다음날 06시까지"},
    {"term": "주의 업종", "definition": "상품권·볼링장·영화관 등"},
]


def test_only_terms_the_question_uses_are_picked():
    picked = pick_terms("고액 결제 건수를 보여줘", TERMS)
    assert [t["term"] for t in picked] == ["고액"]


def test_a_term_with_a_space_still_matches():
    picked = pick_terms("주의업종 사용 내역", TERMS)
    assert [t["term"] for t in picked] == ["주의 업종"]


def test_no_matching_term_means_none():
    assert pick_terms("카드별 합계", TERMS) == []


# --- build_context ------------------------------------------------------

def test_the_context_lists_examples_and_terms():
    text = build_context(
        user_context="",
        examples=[BOOKMARKS[0]],
        terms=[TERMS[0]],
    )
    assert "SELECT merchname FROM v_approval" in text
    assert "고액: 한 건 결제금액이 50만원 이상" in text


def test_the_users_own_context_is_kept():
    assert "이전 질문" in build_context("이전 질문", [], [])


def test_nothing_to_add_is_an_empty_context():
    assert build_context("", [], []) == ""


# --- retry --------------------------------------------------------------

def test_a_retry_shows_the_failed_sql_and_the_database_error():
    text = retry_context("SELECT bad FROM t", 'column "bad" does not exist')
    assert "SELECT bad FROM t" in text
    assert 'column "bad" does not exist' in text


def test_a_long_error_is_cut_short():
    assert len(retry_context("SELECT 1", "x" * 5000)) < 1500


# --- follow-up questions -------------------------------------------------

def test_a_follow_up_carries_the_previous_question_and_sql():
    text = build_context("", [], [], previous={"question": "가맹점별 승인금액 합계", "sql": "SELECT merchname FROM v_approval"})
    assert "가맹점별 승인금액 합계" in text
    assert "SELECT merchname FROM v_approval" in text
    assert "follow-up" in text.lower()


def test_a_follow_up_asks_for_a_complete_standalone_sql():
    text = build_context("", [], [], previous={"question": "q", "sql": "SELECT 1"})
    assert "complete" in text.lower()


def test_no_previous_turn_adds_nothing():
    assert build_context("", [], [], previous=None) == ""
    assert build_context("", [], [], previous={"question": "", "sql": ""}) == ""


def test_a_very_long_previous_sql_is_cut():
    text = build_context("", [], [], previous={"question": "q", "sql": "SELECT " + "x, " * 2000})
    assert len(text) < 3000
