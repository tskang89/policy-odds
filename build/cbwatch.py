# -*- coding: utf-8 -*-
"""ECB·일본은행 — Central Bank Watch 공개 수치.

CME 가 €STRWatch 를 유료로 돌려 ECB 쪽 공개 수치를 그쪽에서 받을 수 없다
("You do not have access to this feature", 2026-10-05 확인). 그래서 무료로
같은 것을 내놓는 ECB Watch 쪽을 쓴다. €STR·OIS 선물로 계산한다고 밝혀 두었고,
회의별 금리 수준 분포를 쪽 안에 JSON 으로 심어 둔다.

**공신력을 분명히 해 둘 것.** 여기는 중앙은행도 거래소도 아닌 제3자다. 연준
칸(CME)과 격이 다르다. 화면에 출처를 그대로 적고 '제3자 모델'이라고 밝힌다.
robots.txt 가 긁는 것을 허용하고(/api/ 만 금지, 크롤 지연 1초) 하루 한 번
두 쪽만 받으므로 그 선을 지킨다.

**분포를 셋으로 묶는 방법.** 심어 둔 자료의 order 가 '오늘 대비 bp'다.
음수는 인하, 0 은 동결, 양수는 인상으로 더한다. 원자료가 이미 100 으로
맞춰져 있어 더하기만 하면 된다.
"""

from __future__ import annotations

import datetime
import re

import fetch

SITE = "https://centralbank.watch"
BANKS = {
    "EA": {"path": "/european-central-bank/", "bank": "ECB",
           "rate": "예금금리"},
    "JP": {"path": "/bank-of-japan/", "bank": "일본은행",
           "rate": "정책금리(무담보 콜 1일)"},
}

# var t=[{bars:[{color:"...",label:"2.50%",order:0,value:91.9}, ...],
#         label:"29-Oct-2026"}, ...]
_GROUP = re.compile(r"\{bars:\[(.*?)\],label:\"([^\"]+)\"\}", re.S)
#   칸 하나를 통째로 집는다. 여기에 괄호를 두면 findall 이 전체가 아니라
#   그 안만 돌려주어 order·value 를 다시 찾을 수 없다.
_BAR = re.compile(r"\{[^{}]*\}")
_ORDER = re.compile(r"order:(-?\d+)")
_VALUE = re.compile(r"value:(-?[\d.]+)")
_LABEL = re.compile(r"label:\"([^\"]*)\"")
_DAY = re.compile(r"^(\d{1,2})-([A-Z][a-z]{2})-(\d{4})$")
_MONTH = {m: i for i, m in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}

# 오늘 기준 예상 경로. 회의별 '반영된 누적 변화(bp)' 를 여기서 가져온다.
_PATH = re.compile(r"todayPath:\s*\[(.*?)\]", re.S)
_PATH_ROW = re.compile(r"\{date:\"(\d{4}-\d{2}-\d{2})\"[^{}]*?"
                       r"meanChangeBps:(-?[\d.]+)")
# 현재 정책금리. '2.50%' 처럼 적혀 있다.
_LEVEL = re.compile(r"Current [^<]{0,40}Rate[^<]{0,20}</[^>]+>\s*"
                    r"<[^>]*>\s*([\d.]+%)", re.S)
_LEVEL2 = re.compile(r"currentRate:\s*(-?[\d.]+)")


def _date(label: str) -> datetime.date | None:
    m = _DAY.match(label.strip())
    if not m or m.group(2) not in _MONTH:
        return None
    try:
        return datetime.date(int(m.group(3)), _MONTH[m.group(2)],
                             int(m.group(1)))
    except ValueError:
        return None


def _bars(blob: str) -> list[tuple[int, float]]:
    out = []
    for bar in _BAR.findall(blob):
        o, v = _ORDER.search(bar), _VALUE.search(bar)
        if o and v:
            out.append((int(o.group(1)), float(v.group(1))))
    return out


def _implied(html: str) -> dict:
    """회의 날짜별 반영된 누적 변화(bp)."""
    m = _PATH.search(html)
    if not m:
        return {}
    return {d: float(bp) for d, bp in _PATH_ROW.findall(m.group(1))}


def fetch_odds(code: str, today: datetime.date | None = None,
               days: int = 100) -> dict:
    today = today or datetime.date.today()
    meta = BANKS[code]
    html = fetch.get(SITE + meta["path"])

    lv = _LEVEL.search(html)
    if lv:
        level = lv.group(1)
    else:
        m2 = _LEVEL2.search(html)
        level = f"{float(m2.group(1)):.2f}%" if m2 else None

    implied = _implied(html)
    meetings = []
    for blob, label in _GROUP.findall(html):
        day = _date(label)
        if not day or not (today <= day <= today + datetime.timedelta(days=days)):
            continue
        bars = _bars(blob)
        if not bars:
            continue
        row = fetch.even_out(fetch.split_bars(bars))
        row["date"] = day.isoformat()
        bp = implied.get(day.isoformat())
        row["bp"] = round(bp, 1) if bp is not None else None
        meetings.append(row)

    meetings.sort(key=lambda r: r["date"])
    if not meetings:
        raise fetch.FetchError(f"{meta['bank']}: 회의 확률을 하나도 읽지 못했다")
    return {
        "code": code, "bank": meta["bank"], "rate": meta["rate"],
        "level": level, "derived": False,
        "source": "Central Bank Watch", "url": SITE + meta["path"],
        "third_party": True,
        "meetings": meetings,
    }
