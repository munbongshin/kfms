"""Passwords, session tokens, masking and audit rules — the security core.

Everything here is pure so the rules can be pinned without a database.
"""
import time

import pytest

from app.auth.audit_rules import is_audited
from app.auth.masking import mask_results, mask_value
from app.auth.security import create_token, hash_password, read_token, verify_password
from app.services.plan_cost import plan_cost

SECRET = "test-secret"


# --- passwords -------------------------------------------------------------

def test_a_password_is_never_stored_as_typed():
    assert "pa55word!" not in hash_password("pa55word!")


def test_the_right_password_verifies():
    assert verify_password("pa55word!", hash_password("pa55word!")) is True


def test_a_wrong_password_does_not():
    assert verify_password("nope", hash_password("pa55word!")) is False


def test_the_same_password_hashes_differently_each_time():
    assert hash_password("same") != hash_password("same")


def test_a_malformed_hash_is_a_failure_not_a_crash():
    assert verify_password("x", "garbage") is False
    assert verify_password("x", "") is False


# --- tokens ----------------------------------------------------------------

def test_a_token_round_trips():
    token = create_token({"uid": 7, "name": "kim", "role": "auditor"}, SECRET, ttl_seconds=60)
    payload = read_token(token, SECRET)
    assert payload["uid"] == 7 and payload["role"] == "auditor"


def test_a_token_signed_with_another_secret_is_refused():
    token = create_token({"uid": 1}, "other", ttl_seconds=60)
    assert read_token(token, SECRET) is None


def test_a_tampered_token_is_refused():
    token = create_token({"uid": 1, "role": "viewer"}, SECRET, ttl_seconds=60)
    body, sig = token.split(".")
    forged = create_token({"uid": 1, "role": "admin"}, "guess", 60).split(".")[0] + "." + sig
    assert read_token(forged, SECRET) is None
    assert read_token(body + "." + "0" * len(sig), SECRET) is None


def test_an_expired_token_is_refused():
    token = create_token({"uid": 1}, SECRET, ttl_seconds=-1)
    assert read_token(token, SECRET) is None


def test_garbage_is_refused():
    assert read_token("", SECRET) is None
    assert read_token("abc", SECRET) is None
    assert read_token("a.b", SECRET) is None


# --- masking ---------------------------------------------------------------

def test_a_card_number_keeps_only_its_ends():
    assert mask_value("cardno", "5598512345678901") == "5598********8901"


def test_a_card_number_is_masked_under_any_column_name():
    # Aliasing (SELECT cardno AS x) must not defeat the mask.
    assert mask_value("x", "5598512345678901") == "5598********8901"


def test_a_resident_number_is_fully_masked():
    assert mask_value("registno", "9001011234567") == "*************"


def test_short_numbers_and_text_are_left_alone():
    assert mask_value("seqno", "00012345") == "00012345"
    assert mask_value("merchname", "농협은행(주)") == "농협은행(주)"


def test_numbers_that_are_not_strings_are_left_alone():
    assert mask_value("seq", 5598512345678901) == 5598512345678901
    assert mask_value("cardno", None) is None


def test_a_card_number_inside_text_is_masked():
    assert mask_value("memo", "카드 5598512345678901 분실") == "카드 5598********8901 분실"


def test_rows_are_masked_for_a_viewer_only():
    rows = [{"cardno": "5598512345678901", "amt": 10}]
    assert mask_results(rows, "viewer")[0]["cardno"] == "5598********8901"
    assert mask_results(rows, "auditor")[0]["cardno"] == "5598512345678901"
    assert mask_results(rows, "admin")[0]["cardno"] == "5598512345678901"


def test_masking_does_not_modify_the_input():
    rows = [{"cardno": "5598512345678901"}]
    mask_results(rows, "viewer")
    assert rows[0]["cardno"] == "5598512345678901"


def test_an_unknown_role_is_treated_as_a_viewer():
    assert mask_results([{"c": "5598512345678901"}], "???")[0]["c"] == "5598********8901"


# --- what gets audited -----------------------------------------------------

@pytest.mark.parametrize("method,path", [
    ("POST", "/api/v1/databases"),
    ("PATCH", "/api/v1/databases/1"),
    ("DELETE", "/api/v1/history"),
    ("PUT", "/api/v1/llm-settings"),
    ("POST", "/api/v1/excel/upload"),
    ("GET", "/api/v1/anomaly/findings/transactions"),
    ("GET", "/api/v1/databases/1/tables/card_data/rows"),
    ("GET", "/api/v1/history/42"),
])
def test_changes_and_sensitive_reads_are_audited(method, path):
    assert is_audited(method, path) is True


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/v1/databases"),
    ("GET", "/api/v1/history"),
    ("GET", "/api/v1/glossary"),
    ("POST", "/api/v1/query/validate"),
    ("POST", "/api/v1/query/generate"),
    ("GET", "/api/v1/auth/me"),
    ("POST", "/api/v1/llm-settings/test"),
])
def test_routine_calls_are_not(method, path):
    assert is_audited(method, path) is False


@pytest.mark.parametrize("path", [
    "/api/v1/query/execute",
    "/api/v1/query/generate-and-execute",
    "/api/v1/auth/login",
    "/api/v1/databases/1/tables/card_data/rows",
])
def test_calls_that_log_their_own_detail_are_skipped_by_the_generic_log(path):
    assert is_audited("POST" if "rows" not in path else "GET", path, generic=True) is False


# --- plan cost -------------------------------------------------------------

def test_the_total_cost_is_read_from_an_explain_json_plan():
    rows = [{"QUERY PLAN": '[{"Plan": {"Total Cost": 1234.5, "Plan Rows": 90}}]'}]
    assert plan_cost(rows) == (1234.5, 90)


def test_an_already_parsed_plan_works_too():
    rows = [{"QUERY PLAN": [{"Plan": {"Total Cost": 10.0, "Plan Rows": 3}}]}]
    assert plan_cost(rows) == (10.0, 3)


def test_no_plan_means_unknown():
    assert plan_cost([]) is None
    assert plan_cost([{"QUERY PLAN": "not json"}]) is None


def test_a_rerun_is_not_logged_twice():
    # It writes its own entry, naming the question; the generic line would only repeat it.
    assert is_audited("POST", "/api/v1/query/rerun/12", generic=True) is False
    assert is_audited("POST", "/api/v1/query/rerun/12") is True
