"""Parsing what OpenAI-compatible servers send back.

LM Studio, vLLM, llama.cpp, LocalAI and Groq all speak the same protocol, but
reasoning models (qwen3, deepseek-r1, gpt-oss) prepend their thinking to the
answer, which must not end up in the SQL.
"""
from app.llm.base import BaseLLMProvider
from app.llm.openai_compatible_provider import model_ids, message_text


def extract(text):
    return BaseLLMProvider.extract_sql_from_response(None, text)


def test_model_ids_are_read_from_the_models_list():
    body = {"object": "list", "data": [{"id": "qwen2.5-coder"}, {"id": "llama-3.1-8b"}]}
    assert model_ids(body) == ["llama-3.1-8b", "qwen2.5-coder"]


def test_a_models_list_without_data_is_empty():
    assert model_ids({}) == []


def test_the_answer_is_the_first_choice():
    body = {"choices": [{"message": {"role": "assistant", "content": "SELECT 1"}}]}
    assert message_text(body) == "SELECT 1"


def test_an_empty_answer_is_an_empty_string():
    assert message_text({"choices": [{"message": {"content": None}}]}) == ""


def test_thinking_is_stripped_before_the_sql():
    answer = "<think>The user wants totals, so GROUP BY…</think>\nSELECT 1"
    assert extract(answer) == "SELECT 1"


def test_thinking_is_stripped_before_a_code_block():
    answer = "<think>hmm ```sql SELECT 2``` no</think>\n```sql\nSELECT 1\n```"
    assert extract(answer) == "SELECT 1"


def test_plain_sql_is_left_alone():
    assert extract("SELECT 1") == "SELECT 1"
