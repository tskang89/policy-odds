# -*- coding: utf-8 -*-
"""한국은행 — 단기금리 커브에서 역산.

연준·ECB·일본은행은 남이 계산해 공개한 것을 옮기지만, 한국은 그런 것이
없다. 그래서 여기만 **내가 계산한다.** 화면에 '역산'이라고 적어 둔다.

쓰는 자료 (ECOS, 날마다)
  기준금리        722Y001 / 0101000
  통안증권 91일   817Y002 / 010400000
  통안증권 1년    817Y002 / 010400001
회의일은 한국은행 공식 일정표에서 받는다.

**셈법.** 만기 91일 금리는 그 사이 하루짜리 금리의 평균이라고 본다. 금리는
금통위 때마다 계단으로 움직이므로, 창 안에 있는 **모든** 회의를 넣고 회의마다
같은 크기 δ 씩 움직인다고 본다. 회의가 t1, t2 … 에 있으면

    (통안91일 - 기준금리 - 프리미엄) × 91 = Σ i × (t_{i+1} - t_i)  × δ

에서 δ 를 얻고, i 번째 회의의 누적 변화는 i × δ 다.

**처음에 두 가지를 틀렸다(2026-10-05, 소장님이 '인상 확률이 너무 높다'고
짚어 주셨다).**

  1. 91일 창 안에 금통위가 **둘** 있는데 하나만 넣었다. 둘째 회의는 1년
     금리로 풀었는데, 1년 금리에는 내년 인상까지 들어 있어 그것을 11월
     한 번에 몰아 붙였다. 11월 인상 확률이 100 으로 나온 까닭이다.
     그래서 **1년 금리는 셈에서 뺐다** — 창 밖의 이야기를 창 안으로 끌어
     오면 안 된다. 보여 주기만 한다.
  2. 기간 프리미엄을 0 으로 놓았다. 2013~2026년 3,388 영업일을 재 보니
     통안 91일은 기준금리보다 **중앙값 +2.5bp** 높다(평균 +1.6bp,
     사분위 -3~+8). 작지만 확률로 바꾸면 10%p 쯤 움직인다.

그래서 **91일 창 안의 회의만** 싣는다. 그 너머는 91일 금리가 말해 주는 바가
없다.

**확률로 바꾸기.** 25bp 한 번을 한 칸으로 보고 선형으로 나눈다. Δ 를 25 로
나눈 것이 k 이면, 아래 칸 floor(k) 에 (1-f), 위 칸 floor(k)+1 에 f 를 준다
(f 는 소수부). 반영분이 +7.5bp 면 k=0.3 → 동결 70, 인상 30. 소장님이 말씀하신
그 환산이다. k 가 1 을 넘으면 '오늘보다 높을 확률'은 100 이 된다 — 한 번은
이미 확실하고 두 번째를 다투는 상태이므로 그것이 맞다.

**믿을 만한 정도.** 관측이 하나(91일)뿐이라 '첫 회의에 올릴지 둘째 회의에
올릴지'는 가릴 수 없다. 회의마다 같은 크기로 움직인다고 본 것은 어느 쪽으로도
기울지 않으려는 가정이지, 시장이 그렇게 본다는 뜻이 아니다. 그래서 반영분(bp)을
화면에 함께 적는다 — 확률만 보이면 실제보다 정밀해 보인다.
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
T91 = 91
CAP = 150.0          # 이보다 큰 반영분은 셈이 어긋난 것으로 본다

# 통안증권 91일이 기준금리보다 평소 얼마나 높은가. 2013-01-02 ~ 2026-10-01,
# 영업일 3,388일의 중앙값이다(평균 +1.6bp, 사분위 -3~+8bp). 기대와 무관하게
# 늘 얹혀 있는 몫이므로 빼고 셈한다. 가끔 다시 재 볼 것 — 제도가 바뀌면
# 이 값도 바뀐다.
PREMIUM_91 = 2.5


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
    import time
    body = json.loads(fetch.get(url))
    rows = body.get("StatisticSearch", {}).get("row", [])
    if not rows:
        # ECOS 는 탈이 나면 StatisticSearch 대신 RESULT 에 까닭을 담아 보낸다.
        # 그 말을 그대로 올려야 무엇이 잘못됐는지 알 수 있다 — '값이 없다'
        # 만으로는 호출이 막힌 것인지 자료가 없는 것인지 가릴 수가 없다.
        why = body.get("RESULT") or next(iter(body.values()), {})
        if isinstance(why, dict) and why.get("CODE"):
            # 호출이 몰려 거부된 것일 수 있다. 한 번 쉬었다 다시 묻는다.
            time.sleep(3)
            body = json.loads(fetch.get(url))
            rows = body.get("StatisticSearch", {}).get("row", [])
            if not rows:
                raise fetch.FetchError(
                    f"ECOS {code}/{item}: {why.get('CODE')} "
                    f"{why.get('MESSAGE', '')}".strip())
        else:
            raise fetch.FetchError(f"ECOS {code}/{item}: 빈 응답")
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

    # 91일 창 안의 회의만. 그 너머는 91일 금리가 말해 주는 바가 없다.
    inside = [d for d in mts if 0 <= (d - today).days < T91]
    if not inside:
        raise fetch.FetchError("한국은행: 91일 안에 금통위가 없다")

    # 가중치 Σ i × (구간 일수). i 는 그 구간까지 지나온 회의 수.
    weight, prev = 0.0, 0
    for i, day in enumerate(inside, start=1):
        t = (day - today).days
        weight += (i - 1) * (t - prev)
        prev = t
    weight += len(inside) * (T91 - prev)
    if weight <= 0:
        raise fetch.FetchError("한국은행: 가중치가 0 이다")

    spread = (y91 - base) * 100 - PREMIUM_91        # bp, 프리미엄을 뺀다
    delta = spread * T91 / weight                   # 회의 한 번치

    meetings_out = []
    for i, day in enumerate(inside, start=1):
        bp = delta * i
        if day > today + datetime.timedelta(days=days) or abs(bp) > CAP:
            continue
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
        # 1년 금리는 셈에 쓰지 않는다. 커브가 어디까지 올라가 있는지
        # 보여 주려고 싣는 것이므로 '참고'라고 적는다.
        "inputs": [("기준금리", f"{base:.2f}%", when_base),
                   ("통안증권 91일", f"{y91:.3f}%", when91),
                   ("통안증권 1년(참고)", f"{y365:.3f}%", when365)],
        "meetings": meetings_out,
    }
