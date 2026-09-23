from app.services.anomaly_service import DETAIL_FIELDS, split_detail


def row(**overrides):
    defaults = {
        "seq": 276618.0,
        "class": "A",
        "cardno": "4072813426841111",
        "transdate": "2023-07-31",
        "transtime": "11:46:12",
        "merchname": "(주)이마트전주점",
        "mccname": "대형할인점",
        "apprtot": 83300.0,
        "appramt": 75727.0,
        "vat": 7573.0,
        "apprno": "30000059",
        "insttype": "A",
        "instmonth": "00",
        "merchbizno": "5063304915",
        "merchtel": "031 355 3185",
        "merchaddr1": "경기 화성시 수노을중앙로 130-0",
        "readflag": "R",
        "datacode": "D",
        "erryn": None,
    }
    defaults.update(overrides)
    return defaults


def test_core_carries_the_audit_fields_in_a_fixed_order():
    core, _ = split_detail(row())
    assert [c["field"] for c in core] == list(DETAIL_FIELDS)


def test_core_shows_the_card_number_unmasked():
    # The reviewer opened this row deliberately; masking here would defeat it.
    core, _ = split_detail(row())
    cardno = next(c for c in core if c["field"] == "cardno")
    assert cardno["value"] == "4072813426841111"


def test_core_entries_carry_a_korean_label():
    core, _ = split_detail(row())
    assert all(c["label"] and c["label"] != c["field"] for c in core)


def test_rest_holds_the_remaining_populated_fields():
    _, rest = split_detail(row())
    fields = {r["field"] for r in rest}
    assert "readflag" in fields
    assert "datacode" in fields


def test_rest_excludes_the_core_fields():
    _, rest = split_detail(row())
    assert not ({r["field"] for r in rest} & set(DETAIL_FIELDS))


def test_rest_drops_empty_values_so_the_toggle_is_not_mostly_blank():
    _, rest = split_detail(row(erryn=None, workdate=""))
    fields = {r["field"] for r in rest}
    assert "erryn" not in fields
    assert "workdate" not in fields


def test_core_keeps_a_missing_audit_field_as_none_rather_than_dropping_it():
    # A blank mccname is itself evidence — 23% of approvals have none.
    core, _ = split_detail(row(mccname=None))
    mcc = next(c for c in core if c["field"] == "mccname")
    assert mcc["value"] is None
