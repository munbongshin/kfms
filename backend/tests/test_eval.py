"""Scoring generated SQL against known answers.

An answer is right when it returns the same data, however it is written: the
column names, the column order and (unless a LIMIT is at stake) the row order
are the model's choice and must not fail a correct answer.
"""
import asyncio
from datetime import date
from decimal import Decimal

from app.services.eval_compare import results_match
from app.services.eval_service import run_evaluation, summarize

ROWS = [{"cat": "Electronics", "total": 156905}, {"cat": "Clothing", "total": 155580}]


# --- results_match ------------------------------------------------------------

def test_identical_results_match():
    assert results_match(ROWS, [dict(r) for r in ROWS])[0] is True


def test_row_order_does_not_matter():
    assert results_match(ROWS, list(reversed(ROWS)))[0] is True


def test_column_names_do_not_matter():
    renamed = [{"카테고리": "Electronics", "총 매출액": 156905}, {"카테고리": "Clothing", "총 매출액": 155580}]
    assert results_match(ROWS, renamed)[0] is True


def test_column_order_does_not_matter():
    swapped = [{"total": 156905, "cat": "Electronics"}, {"total": 155580, "cat": "Clothing"}]
    assert results_match(ROWS, swapped)[0] is True


def test_numeric_types_are_compared_by_value():
    exp = [{"n": 5}, {"n": Decimal("2.50")}]
    act = [{"x": 5.0}, {"x": 2.5}]
    assert results_match(exp, act)[0] is True


def test_tiny_float_noise_is_ignored():
    assert results_match([{"n": 0.1 + 0.2}], [{"n": 0.3}])[0] is True


def test_different_values_do_not_match():
    wrong = [{"cat": "Electronics", "total": 1}, {"cat": "Clothing", "total": 155580}]
    ok, reason = results_match(ROWS, wrong)
    assert ok is False and "값" in reason


def test_a_different_row_count_is_reported():
    ok, reason = results_match(ROWS, ROWS[:1])
    assert ok is False and "행 수" in reason and "2" in reason and "1" in reason


def test_a_different_column_count_is_reported():
    ok, reason = results_match(ROWS, [{"cat": "Electronics"}, {"cat": "Clothing"}])
    assert ok is False and "열 수" in reason


def test_nulls_and_dates_compare_sensibly():
    assert results_match([{"a": None, "d": date(2024, 1, 2)}], [{"z": None, "y": "2024-01-02"}])[0] is True


def test_both_empty_is_a_match():
    assert results_match([], [])[0] is True


def test_empty_versus_data_is_not():
    assert results_match([], ROWS)[0] is False


def test_repeated_rows_are_counted():
    # Two identical rows are not the same answer as one.
    assert results_match([{"a": 1}, {"a": 1}], [{"a": 1}])[0] is False
    assert results_match([{"a": 1}, {"a": 1}], [{"a": 1}, {"a": 1}])[0] is True


# --- run_evaluation ---------------------------------------------------------------

def case(i, q="q", sql="SELECT 1"):
    return {"id": i, "question": f"{q}{i}", "expected_sql": sql}


def run(cases, generate, execute, progress=None):
    return asyncio.run(run_evaluation(cases, generate, execute, progress or (lambda *_: None)))


def test_a_case_passes_when_the_results_match():
    async def generate(q): return "SELECT a"
    async def execute(sql): return [{"a": 1}]
    out = run([case(1)], generate, execute)
    assert out[0]["passed"] is True and out[0]["generated_sql"] == "SELECT a"


def test_a_case_fails_when_the_results_differ():
    async def generate(q): return "SELECT wrong"
    async def execute(sql): return [{"a": 2}] if sql == "SELECT wrong" else [{"a": 1}]
    out = run([case(1)], generate, execute)
    assert out[0]["passed"] is False and out[0]["reason"]


def test_a_generation_error_fails_only_that_case():
    async def generate(q):
        if q.endswith("1"):
            raise RuntimeError("llm down")
        return "SELECT a"
    async def execute(sql): return [{"a": 1}]
    out = run([case(1), case(2)], generate, execute)
    assert out[0]["passed"] is False and "llm down" in out[0]["reason"]
    assert out[1]["passed"] is True


def test_an_execution_error_is_a_failure_not_a_crash():
    async def generate(q): return "SELECT bad"
    async def execute(sql):
        if sql == "SELECT bad":
            raise RuntimeError('column "bad" does not exist')
        return [{"a": 1}]
    out = run([case(1)], generate, execute)
    assert out[0]["passed"] is False and "bad" in out[0]["reason"]


def test_a_broken_expected_sql_is_reported_as_such():
    # A case whose own answer does not run must not blame the model.
    async def generate(q): return "SELECT a"
    async def execute(sql):
        if sql == "SELECT broken":
            raise RuntimeError("syntax error")
        return [{"a": 1}]
    out = run([case(1, sql="SELECT broken")], generate, execute)
    assert out[0]["passed"] is False and "정답 SQL" in out[0]["reason"]


def test_progress_is_reported_after_each_case():
    async def generate(q): return "SELECT a"
    async def execute(sql): return [{"a": 1}]
    seen = []
    run([case(1), case(2), case(3)], generate, execute, lambda done, total, results: seen.append((done, total)))
    assert seen == [(1, 3), (2, 3), (3, 3)]


def test_the_summary_counts_and_rates():
    s = summarize([{"passed": True}, {"passed": True}, {"passed": False}, {"passed": True}])
    assert s == {"total": 4, "passed": 3, "rate": 75.0}


def test_an_empty_summary_has_no_rate():
    assert summarize([]) == {"total": 0, "passed": 0, "rate": 0.0}
