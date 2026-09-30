"""Messages in the language the screen is set to.

The screens send Accept-Language; the server writes Korean and translates on the
way out for English, leaving data (query results, names from the database) alone.
"""
from app.i18n import language_of, translate, translate_body, translate_json
import json


# --- the language asked for -----------------------------------------------------------------------

def test_english_is_recognised_from_the_header():
    assert language_of("en") == "en"
    assert language_of("en-US,en;q=0.9") == "en"
    assert language_of("EN") == "en"


def test_anything_else_is_korean():
    for header in (None, "", "ko", "ko-KR", "fr", "de-DE"):
        assert language_of(header) == "ko"


# --- messages --------------------------------------------------------------------------------------

def test_an_exact_message_is_translated():
    assert translate("사용자를 찾을 수 없습니다", "en") == "User not found"


def test_korean_is_left_as_it_is():
    assert translate("사용자를 찾을 수 없습니다", "ko") == "사용자를 찾을 수 없습니다"


def test_a_message_with_a_variable_part_is_translated_and_keeps_the_part():
    assert translate("'서울' 이름의 연결이 이미 있습니다", "en") == "A connection named '서울' already exists"


def test_a_message_that_is_not_known_is_returned_unchanged():
    assert translate("처음 보는 문장입니다", "en") == "처음 보는 문장입니다"


def test_text_without_hangul_is_never_touched():
    assert translate("column does not exist", "en") == "column does not exist"


def test_the_most_specific_template_wins():
    # "단건 {amount}" would also match the longer one.
    text = "단건 120,000원 (영화관 기준 100,000원 이상)"
    assert translate(text, "en") == "Single payment 120,000 KRW (threshold for 영화관: 100,000 KRW or more)"
    assert translate("단건 6,000,000원", "en") == "Single payment 6,000,000 KRW"


def test_parts_inside_a_message_are_translated_too():
    assert translate("주말 결제 — 토요일 12:25", "en") == "Weekend payment — Sat 12:25"


def test_a_data_value_inside_a_message_is_kept():
    assert translate("공휴일(광복절) 결제 — 화요일 14:00", "en") == "Holiday (광복절) payment — Tue 14:00"


def test_messages_joined_by_a_separator_are_translated_piece_by_piece():
    text = "2026년: 공공데이터포털에 연결하지 못했습니다 / 2027년: 공공데이터포털에 연결하지 못했습니다"
    assert translate(text, "en") == "2026: Could not connect to the Public Data Portal / 2027: Could not connect to the Public Data Portal"


def test_a_change_note_is_translated():
    assert translate("23시 → 22시", "en") == "23:00 → 22:00"
    assert translate("켜짐 → 꺼짐", "en") == "On → Off"
    assert translate("500,000 → 300,000", "en") == "500,000 → 300,000"


def test_a_category_table_change_note_is_translated_with_the_names_kept():
    assert translate("영화관 100,000→150,000원, +항공사 2,000,000원", "en") == "영화관 100,000→150,000 KRW, +항공사 2,000,000 KRW"


# --- JSON --------------------------------------------------------------------------------------------

def test_messages_are_translated_under_message_keys():
    assert translate_json({"detail": "사용자를 찾을 수 없습니다"}, "en") == {"detail": "User not found"}


def test_a_list_of_warnings_is_translated_item_by_item():
    out = translate_json({"validation": {"warnings": ["SQL이 비어 있습니다", "x"]}}, "en")
    assert out["validation"]["warnings"] == ["The SQL is empty", "x"]


def test_nested_settings_are_translated():
    settings = {"rules": [{"label": "고액 결제", "params": [{"label": "심각도", "hint": "결과 목록의 정렬과 표시에 쓰입니다"}]}]}
    out = translate_json(settings, "en")
    assert out["rules"][0]["label"] == "High-value payment"
    assert out["rules"][0]["params"][0] == {"label": "Severity", "hint": "Used to sort and show the result list"}


def test_data_is_never_translated_even_if_it_looks_like_a_message():
    payload = {
        "results": [{"label": "고액 결제", "message": "사용자를 찾을 수 없습니다"}],
        "schema": {"t": [{"name": "a", "label": "카드번호"}]},
        "transactions": [{"core": [{"label": "카드번호"}]}],
        "columns": [{"label": "금액"}],
    }
    assert translate_json(payload, "en") == payload


def test_values_under_other_keys_are_left_alone():
    assert translate_json({"name": "고액 결제", "question": "사용자를 찾을 수 없습니다"}, "en") == {
        "name": "고액 결제", "question": "사용자를 찾을 수 없습니다"}


def test_korean_requests_are_not_walked_at_all():
    payload = {"detail": "사용자를 찾을 수 없습니다"}
    assert translate_json(payload, "ko") is payload


def test_a_response_body_is_translated_and_stays_valid_json():
    body = json.dumps({"detail": "사용자를 찾을 수 없습니다"}, ensure_ascii=False).encode()
    assert json.loads(translate_body(body, "en")) == {"detail": "User not found"}


def test_a_body_that_is_not_json_comes_back_as_it_was():
    assert translate_body(b"PK\x03\x04binary", "en") == b"PK\x03\x04binary"


# --- the whole request ------------------------------------------------------------------------------

def test_an_english_request_gets_english_messages_and_a_correct_length():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    english = client.get("/api/v1/databases", headers={"Accept-Language": "en"})
    korean = client.get("/api/v1/databases")
    assert english.json() == {"detail": "Sign-in required"}
    assert korean.json() == {"detail": "로그인이 필요합니다"}
    assert int(english.headers["content-length"]) == len(english.content)


def test_a_merchant_name_ending_in_a_unit_is_not_read_as_an_amount():
    assert translate("주의 업종: 화   원", "en") == "Watch category: 화   원"
    assert translate("동일 가맹점 60분 이내 2건 142,060원", "en") == "Same merchant: 2 within 60 min, total 142,060 KRW"
