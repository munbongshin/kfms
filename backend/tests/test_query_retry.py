"""Generated SQL that the database rejects is sent back to the model to fix."""
import asyncio
from types import SimpleNamespace

from app.services.query_service import MAX_RETRIES, QueryService


class FakeLLM:
    def __init__(self, answers):
        self.answers = list(answers)
        self.contexts = []
        self.label_overrides = []

    async def generate_sql(self, question, connection_pool, database_id, context="", excluded_tables=None,
                           label_overrides=None):
        self.contexts.append(context)
        self.label_overrides.append(label_overrides)
        sql = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        return {"sql": sql, "provider": "fake", "model": "m"}


class FakePool:
    """Plans cleanly unless the SQL mentions the bad column."""

    def __init__(self):
        self.explained = []

    async def execute_query(self, database_id, sql, params=None):
        self.explained.append(sql)
        if "badcol" in sql:
            raise RuntimeError('column "badcol" does not exist')
        return []


class FakeHistory:
    def __init__(self, saved=()):
        self.saved = saved

    async def get_all(self, **kwargs):
        return list(self.saved)


class FakeGlossary:
    async def list_all(self):
        return [SimpleNamespace(term="고액", definition="한 건 50만원 이상")]


def service(llm, pool=None, history=None, glossary=None, labels=None):
    return QueryService(pool or FakePool(), history or FakeHistory(), llm, glossary_repo=glossary, label_repo=labels)


def run(coro):
    return asyncio.run(coro)


def test_a_clean_sql_is_used_as_is():
    llm = FakeLLM(["SELECT 1 FROM t"])
    out = run(service(llm).generate_sql("q", "1"))
    assert out["attempts"] == 1
    assert len(llm.contexts) == 1


class FakeLabels:
    def __init__(self, rows=None, fail=False):
        self.rows, self.fail = rows or [], fail

    async def overrides(self, connection_id):
        if self.fail:
            raise RuntimeError("metadata database is down")
        return self.rows


def test_the_administrators_column_names_reach_the_llm():
    rows = [object()]
    llm = FakeLLM(["SELECT 1 FROM t"])
    run(service(llm, labels=FakeLabels(rows)).generate_sql("q", "1"))
    assert llm.label_overrides == [rows]


def test_a_label_lookup_failure_never_blocks_a_question():
    llm = FakeLLM(["SELECT 1 FROM t"])
    out = run(service(llm, labels=FakeLabels(fail=True)).generate_sql("q", "1"))
    assert out["sql"] and llm.label_overrides == [[]]


def test_a_failing_sql_is_retried_with_the_database_error():
    llm = FakeLLM(["SELECT badcol FROM t", "SELECT ok FROM t"])
    out = run(service(llm).generate_sql("q", "1"))
    assert out["attempts"] == 2
    assert "SELECT ok" in out["sql"]
    assert 'column "badcol" does not exist' in llm.contexts[1]
    assert "SELECT badcol FROM t" in llm.contexts[1]


def test_retries_stop_after_the_limit_and_the_error_is_shown():
    llm = FakeLLM(["SELECT badcol FROM t"])
    out = run(service(llm).generate_sql("q", "1"))
    assert out["attempts"] == MAX_RETRIES + 1
    assert any("badcol" in w for w in out["validation"]["warnings"])


def test_an_unsafe_sql_is_not_sent_to_the_database():
    pool = FakePool()
    llm = FakeLLM(["DROP TABLE t"])
    out = run(service(llm, pool).generate_sql("q", "1"))
    assert out["validation"]["is_safe"] is False
    assert pool.explained == []
    assert out["attempts"] == 1


def test_the_dry_run_plans_the_query_without_running_it():
    pool = FakePool()
    run(service(FakeLLM(["SELECT 1 FROM t"]), pool).generate_sql("q", "1"))
    assert pool.explained[0].startswith("EXPLAIN ")


def test_bookmarked_examples_reach_the_prompt():
    saved = [SimpleNamespace(question="가맹점별 승인금액 합계 상위 5건", generated_sql="SELECT merchname FROM v_approval")]
    llm = FakeLLM(["SELECT 1 FROM t"])
    out = run(service(llm, history=FakeHistory(saved)).generate_sql("가맹점별 승인금액 합계", "1"))
    assert "SELECT merchname FROM v_approval" in llm.contexts[0]
    assert out["examples_used"] == 1


def test_glossary_terms_the_question_uses_reach_the_prompt():
    llm = FakeLLM(["SELECT 1 FROM t"])
    out = run(service(llm, glossary=FakeGlossary()).generate_sql("고액 결제 건수", "1"))
    assert "고액: 한 건 50만원 이상" in llm.contexts[0]
    assert out["terms_used"] == ["고액"]


def test_broken_guidance_never_blocks_a_question():
    class Broken:
        async def get_all(self, **kwargs):
            raise RuntimeError("history down")

        async def list_all(self):
            raise RuntimeError("glossary down")

    llm = FakeLLM(["SELECT 1 FROM t"])
    out = run(service(llm, history=Broken(), glossary=Broken()).generate_sql("q", "1"))
    assert out["attempts"] == 1


def test_examples_can_be_switched_off_for_an_evaluation():
    # Scoring the model on a bookmarked question while showing it that very
    # bookmark would measure nothing.
    saved = [SimpleNamespace(question="가맹점별 승인금액 합계", generated_sql="SELECT merchname FROM v_approval")]
    llm = FakeLLM(["SELECT 1 FROM t"])
    out = run(service(llm, history=FakeHistory(saved)).generate_sql("가맹점별 승인금액 합계", "1", use_examples=False))
    assert "SELECT merchname" not in llm.contexts[0]
    assert out["examples_used"] == 0
