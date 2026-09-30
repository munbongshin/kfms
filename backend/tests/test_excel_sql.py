"""SQL for loading an Excel sheet into its own table.

Headers come straight from a user's spreadsheet: Korean, spaces, brackets,
numbers first, even quotes. None of that may break the SQL or be injected
into it. Uploads live in their own schema so they never mix with source data.
"""
import datetime

import numpy as np
import pandas as pd

from app.services.excel_service import (
    UPLOAD_SCHEMA,
    build_create_table,
    build_insert,
    row_params,
    upload_table_key,
)


def test_uploads_go_to_their_own_schema():
    assert UPLOAD_SCHEMA == "kfms_upload"
    assert upload_table_key("excel_upload_1_ab") == "kfms_upload.excel_upload_1_ab"


def test_create_table_quotes_the_schema_the_table_and_every_column():
    sql = build_create_table("kfms_upload.t1", {"과제명": "TEXT", "총 연구기간": "NUMERIC"})
    assert sql.startswith('CREATE TABLE "kfms_upload"."t1" (')
    assert '"과제명" TEXT' in sql
    assert '"총 연구기간" NUMERIC' in sql


def test_a_quote_in_a_header_cannot_break_out():
    sql = build_create_table("kfms_upload.t1", {'a"b': "TEXT"})
    assert '"a""b" TEXT' in sql


def test_a_non_text_header_is_used_as_text():
    # pandas gives integer column names to sheets whose header row is numeric.
    sql = build_create_table("kfms_upload.t1", {2023: "INTEGER"})
    assert '"2023" INTEGER' in sql


def test_insert_binds_by_position_not_by_header():
    # ":총 연구기간" or ":2023년" is not a valid bind name; positions always are.
    sql = build_insert("kfms_upload.t1", 3)
    assert sql == 'INSERT INTO "kfms_upload"."t1" VALUES (:p0, :p1, :p2)'


def test_row_values_are_bound_in_column_order():
    assert row_params(["a", 1, None]) == {"p0": "a", "p1": 1, "p2": None}


def test_missing_values_become_null():
    params = row_params([np.nan, pd.NaT, None])
    assert params == {"p0": None, "p1": None, "p2": None}


def test_numpy_numbers_become_plain_python_numbers():
    # The database driver rejects numpy scalars.
    params = row_params([np.int64(7), np.float64(1.5), np.bool_(True)])
    assert params == {"p0": 7, "p1": 1.5, "p2": True}
    assert type(params["p0"]) is int
    assert type(params["p1"]) is float


def test_timestamps_become_datetimes():
    params = row_params([pd.Timestamp("2024-01-02 03:04:05")])
    assert params["p0"] == datetime.datetime(2024, 1, 2, 3, 4, 5)


# --- table name from the file name ------------------------------------------

from app.services.excel_service import table_name_from  # noqa: E402


def test_the_file_name_becomes_the_table_name():
    assert table_name_from("제재현황.xlsx") == "제재현황"


def test_spaces_and_symbols_become_underscores():
    assert table_name_from("2024 제재 현황(최종).xlsx") == "t_2024_제재_현황_최종"


def test_english_is_lower_cased_so_it_works_unquoted():
    assert table_name_from("Sales Report-Q1.xls") == "sales_report_q1"


def test_a_name_starting_with_a_digit_gets_a_prefix():
    assert table_name_from("2024.xlsx") == "t_2024"


def test_system_prefixes_are_avoided():
    assert table_name_from("pg_stats.xlsx") == "t_pg_stats"


def test_a_name_of_only_symbols_falls_back():
    assert table_name_from("###.xlsx") == "excel_upload"


def test_the_name_fits_postgres_63_byte_limit_without_splitting_a_character():
    name = table_name_from("가" * 40 + ".xlsx")
    assert len(name.encode("utf-8")) <= 63
    assert name == "가" * 21


def test_a_typed_name_gets_the_same_treatment():
    assert table_name_from("  My Table  ") == "my_table"


def test_a_clean_name_is_left_alone():
    assert table_name_from("approval_2024") == "approval_2024"
