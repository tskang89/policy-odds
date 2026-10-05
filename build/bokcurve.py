# -*- coding: utf-8 -*-
"""한국은행 — 단기금리 커브에서 역산.

연준·ECB·일본은행은 남이 계산해 공개한 것을 옮기지만, 한국은 그런 것이
없다. 그래서 여기만 **내가 계산한다.** 화면에 '역산'이라고 적어 둔다.

쓰는 자료 (ECOS, 날마다)
  기준금리        722Y001 / 0101000
  통안증권 91일   817Y002 / 010400000
  통안증권 1년    817Y002 / 010400001
회의일은 한국은행 공식 일정표에서 받는다.

**셈법.** 만기 T 일 금리는 그 사이 하루짜리 금리의 평균이라고 본다. 금리가
회의 때마다 계단으로 움직인다고 하면, 첫 회의가 T 안의 t 일에 있을 때

    y(T) - 기준금리 = Δ1 × (T - t) / T

이고 여기서 Δ1 을 얻는다. 둘째 회의는 1년 금리로 같은 식을 한 번 더 쓴다 —
Δ1 을 이미 알므로 남는 미지수가 Δ2 하나다.

**확률로 바꾸기.** 25bp 한 번을 한 칸으로 보고 선형으로 나눈다. Δ 를 25 로
나눈 것이 k 이면, 아래 칸 floor(k) 에 (1-f), 위 칸 floor(k)+1 에 f 를 준다
(f 는 소수부). 반영분이 +7.5bp 면 k=0.3 → 동결 70, 인상 30. 소장님이 말씀하신
그 환산이다. k 가 1 을 넘으면 '오늘보다 높을 확률'은 100 이 된다 — 한 번은
이미 확실하고 두 번째를 다투는 상태이므로 그것이 맞다.

**믿을 만한 정도.** 통안증권에는 기간 프리미엄이 조금 섞여 있어 인상 쪽으로
치우친다. 둘째 회의는 '그 뒤로는 더 안 움직인다'고 가정한 값이라 더 거칠다.
그래서 반영분(bp)을 화면에 함께 적는다 — 확률만 보이면 정밀해 보인다.
"""

from __future__ import annotations

import datetime
import os
import re

import fetch

ECOS = "https://ecos.bok.or.kr/api"
BOK_SCHEDULE = ("https://www.bok.or.kr/portal/singl/crncyPolicyDrcMtg/"
                "listYear.do?mtgSe=A&menuNo=200755")
_YEAR = re.compile(r"<h3>(\d{4})년</h3>")
_DAY = re.compile(r"(\d{2})월\s*(\d{2})일\(")

STEP = 25.0          # 한 번 움직임(bp)
T91, T365 = 91, 365
CAP = 150.0          # 이보다 큰 반영분은 셈이 어긋난 것으로 본다


def _key() -> str:
    key = os.environ.get("ECOS_API_KEY")
    if not key:
        raise fetch.FetchError("ECOS_API_KEY 가 없다")
    return key


def _latest(code: str, item: str, days: int = 30) -> tuple[str, float]:
    """마지막 관측(날짜, 값). 휴일이 끼면 며칠 전 것이 온다."""
    end = datetime.date.today()
    start = end - datetime.timedelta(days=days)
    url = (f"{ECOS}/StatisticSearch/{_key()}/json/kr/1/100/{code}/D/"
           f"{start:%Y%m%d}/{end:%Y%m%d}/{item}")
    import json
    body = json.loads(fetch.get(url))
    rows = body.get("StatisticSearch", {}).get("row", [])
    vals = [(r["TIME"], float(r["DATA_VALUE"])) for r in rows
            if r.get("DATA_VALUE") not in (None, "", "-")]
    if not vals:
        raise fetch.FetchError(f"ECOS {code}/{item}: 값이 없다")
    return max(vals)


def meetings(today: datetime.date) -> list[datetime.date]:
    out = []
    for year in (today.year, today.year + 1):
        doc = fetch.get(f"{BOK_SCHEDULE}&pYear={year}")
        shown = _YEAR.search(doc)
        if not shown or int(shown.group(1)) != year:
            continue
        for m in _DAY.finditer(doc):
            try:
                out.append(datetime.date(year, int(m.group(1)),
                                         int(m.group(2))))
            except ValueError:
                continue
    out = sorted({d for d in out if d >= today})
    if not out:
        raise fetch.FetchError("한국은행: 회의일을 하나도 읽지 못했다")
    return out


def _odds(bp: float) -> dict:
    """반영분(bp) 을 인하·동결·인상으로. 25bp 한 칸을 선형으로 나눈다."""
    k = bp / STEP
    lo = int(k // 1)                     # 아래 칸 (음수도 바르게 내림한다)
    f = k - lo
    weight = {lo: 1.0 - f, lo + 1: f}
    cut = float(sum(w for n, w in weight.items() if n < 0))
    hold = float(weight.get(0, 0.0))
    hike = float(sum(w for n, w in weight.items() if n > 0))
    return fetch.even_out({"cut": round(100 * cut, 1),
                           "hold": round(100 * hold, 1),
                           "hike": round(100 * hike, 1)})


def fetch_odds(today: datetime.date | None = None,
               days: int = 100) -> dict:
    today = today or datetime.date.today()
    when_base, base = _latest("722Y001", "0101000", days=120)
    when91, y91 = _latest("817Y002", "010400000")
    when365, y365 = _latest("817Y002", "010400001")
    mts = meetings(today)

    rows = []
    d1 = (mts[0] - today).days
    # 첫 회의. 91일 창이 그 회의를 품고 있어야 식이 선다.
    if 0 <= d1 < T91:
        bp1 = (y91 - base) * 100 * T91 / (T91 - d1)
    else:
        bp1 = (y365 - base) * 100 * T365 / max(T365 - d1, 1)
    rows.append((mts[0], bp1))

    # 둘째 회의. 1년 창에서 첫 회의 몫을 덜어 내고 남은 것을 준다.
    if len(mts) > 1:
        d2 = (mts[1] - today).days
        if 0 <= d2 < T365:
            span = (y365 - base) * 100 * T365
            bp2 = (span - bp1 * (d2 - d1)) / (T365 - d2)
            rows.append((mts[1], bp2))

    meetings_out = []
    for day, bp in rows:
        if day > today + datetime.timedelta(days=days):
            continue
        if abs(bp) > CAP:
            continue                     # 셈이 어긋났다 — 싣지 않는다
        row = _odds(bp)
        row["date"] = day.isoformat()
        row["bp"] = round(bp, 1)
        meetings_out.append(row)

    if not meetings_out:
        raise fetch.FetchError("한국은행: 쓸 만한 회의가 없다")
    return {
        "code": "KR", "bank": "한국은행", "rate": "기준금리",
        "level": f"{base:.2f}%", "derived": True,
        "source": "한국은행 ECOS 단기금리에서 역산", "url": BOK_SCHEDULE,
        "inputs": [("기준금리", f"{base:.2f}%", when_base),
                   ("통안증권 91일", f"{y91:.3f}%", when91),
                   ("통안증권 1년", f"{y365:.3f}%", when365)],
        "meetings": meetings_out,
    }
