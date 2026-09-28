"""Short on-screen names for columns whose business name is too long to read.

The column comments come verbatim from the definition workbook
(법인카드 테이블 정보 정리_*.xlsx) and some carry notes in brackets, e.g.
appramt is "공급가액[승인금액,현지금액]". The full text stays in the database
and in the SQL prompt; the screen shows the name users actually say.

Keyed by column name, so a view column gets the same name as its card_data
column. Add an entry here to shorten another header.

The SQL prompt uses these names too, so a term the users do not use (현지금액)
cannot leak into the Korean aliases the model writes.
"""
from typing import Dict

DISPLAY_NAMES: Dict[str, str] = {
    # 현지금액 is workbook notation only; users do not say it.
    "appramt": "승인금액",        # 공급가액[승인금액,현지금액]
    "apprtot": "승인합계",        # 승인합계[현지금액]
    "curracqutot": "매입원금",    # 매입원금[현지금액]
}
