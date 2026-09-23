from app.anomaly.rules import SOURCES
from app.services.anomaly_service import split_detail

APPROVAL = SOURCES["approval"]
ACQUIRE = SOURCES["acquire"]
BILL = SOURCES["bill"]


def row(**overrides):
    defaults = {
        "seq": 276618.0,
        "class": "A",
        "cardno": "4072813426841111",
        "transdate": "2023-07-31",
        "transtime": "11:46:12",
        "merchname": "(주)이마트전주점",
        "mccname": "대형할인점",
        "merchno": "000049877848",
        "merchbizno": "5063304915",
        "apprtot": 83300.0,
        "appramt": 75727.0,
        "vat": 7573.0,
        "apprno": "30000059",
        "insttype": "A",
        "instmonth": "00",
        "merchtel": "031 355 3185",
        "merchaddr1": "경기 화성시 수노을중앙로 130-0",
        "readflag": "R",
        "datacode": "D",
        "erryn": None,
    }
    defaults.update(overrides)
    return defaults


def labelled(core, label):
    return next(c for c in core if c["label"] == label)


def test_core_shows_the_card_number_unmasked():
    # The reviewer opened this row deliberately; masking here would defeat it.
    core, _ = split_detail(row(), APPROVAL)
    assert labelled(core, "카드번호")["value"] == "4072813426841111"


def test_core_labels_the_sources_own_date_column():
    core, _ = split_detail(row(), APPROVAL)
    assert labelled(core, "사용일자")["field"] == "transdate"


def test_another_source_labels_its_differently_named_date_column():
    # 매입내역 dates rows with apprdate, not transdate — same label, same meaning.
    acquire_row = row(apprdate="2023-07-31", purchtime="11:46:12")
    core, _ = split_detail(acquire_row, ACQUIRE)
    assert labelled(core, "사용일자")["field"] == "apprdate"
    assert labelled(core, "사용일자")["value"] == "2023-07-31"


def test_a_source_without_a_column_simply_omits_that_label():
    # 청구내역 carries no transaction time, merchant number or category.
    core, _ = split_detail(row(orgnapprdate="2023-07-27", biltot=1000.0), BILL)
    labels = {c["label"] for c in core}
    assert "사용시각" not in labels
    assert "업종" not in labels
    assert "가맹점번호" not in labels
    assert "카드번호" in labels


def test_core_keeps_a_missing_audit_field_as_none_rather_than_dropping_it():
    # A blank 업종 is itself evidence — 23% of approvals have none.
    core, _ = split_detail(row(mccname=None), APPROVAL)
    assert labelled(core, "업종")["value"] is None


def test_rest_holds_the_remaining_populated_fields():
    _, rest = split_detail(row(), APPROVAL)
    fields = {r["field"] for r in rest}
    assert "readflag" in fields
    assert "datacode" in fields


def test_rest_excludes_everything_already_shown_in_core():
    core, rest = split_detail(row(), APPROVAL)
    assert not ({r["field"] for r in rest} & {c["field"] for c in core})


def test_rest_drops_empty_values_so_the_toggle_is_not_mostly_blank():
    _, rest = split_detail(row(erryn=None, workdate=""), APPROVAL)
    fields = {r["field"] for r in rest}
    assert "erryn" not in fields
    assert "workdate" not in fields
