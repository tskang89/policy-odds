# -*- coding: utf-8 -*-
"""연준 — CME 페드워치 공개 수치.

확률을 내가 계산하지 않는다. CME 가 연방기금 선물로 계산해 내놓은 것을
그대로 옮긴다.

**주의 — 왜 cmegroup.com 이 아닌가.** www.cmegroup.com 은 Akamai 가 코드
접속을 막는다(403, 헤더를 어떻게 꾸며도 같다). 도구 자체는 QuikStrike 라는
다른 호스트에 올라가 있고 그쪽은 막혀 있지 않다. 화면에 쓰는 출처 링크는
사람이 보는 CME 쪽으로 둔다 — 사람은 브라우저로 열므로 막히지 않는다.

**세 숫자의 뜻.** '오늘 목표범위보다 낮을/같을/높을 확률'이다. 그 회의에서
새로 움직일 확률이 아니다. 12월 칸의 인상 확률에는 10월에 올릴 가능성이
이미 들어 있다. CME 쪽 표기(Ease / No Change / Hike)도 같은 뜻이다.
회의 칸끼리 더하거나 비교하면 같은 움직임을 두 번 세게 된다.
"""

from __future__ import annotations

import datetime
import re

import fetch

HOST = "https://cmegroup-tools.quikstrike.net/User/"
TOOL = HOST + "QuikStrikeView.aspx?viewitemid=IntegratedFedWatchTool"
# 사람이 보는 쪽. 각주에서 이 주소로 보낸다.
PUBLIC = "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"

# 'Ease | No Change | Hike' 바로 뒤에 세 숫자가 붙는다.
_TRIPLE = re.compile(
    r"Ease.*?No Change.*?Hike.*?([\d.]+)\s*%.*?([\d.]+)\s*%.*?([\d.]+)\s*%",
    re.S)
_TITLE = re.compile(r"Target Rate Probabilities for ([^\"]+?) Fed Meeting")
_LEVEL = re.compile(r"Current target rate is ([\d]+)-([\d]+)")

# 회의를 바꾸는 단추. ASP.NET 되돌림(postback)이라 __VIEWSTATE 를 함께 보낸다.
_TAB = ("ctl00$MainContent$ucViewControl_IntegratedFedWatchTool"
        "$uccv$lvMeetings$ctrl{idx}$lbMeeting")
_MEETING_BTN = re.compile(
    r'id="ctl00_MainContent_ucViewControl_IntegratedFedWatchTool_uccv'
    r'_lvMeetings_ctrl(\d+)_lbMeeting"[^>]*>(.*?)</a>', re.S)
_HIDDEN = ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION")
_LABEL = re.compile(r"(\d{1,2})\s*([A-Z][a-z]{2})\s*(\d{2})")
_MONTH = {m: i for i, m in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}


def _state(html: str) -> dict:
    out = {"__EVENTARGUMENT": ""}
    for name in _HIDDEN:
        m = re.search(rf'name="{name}" id="[^"]*" value="([^"]*)"', html)
        if m:
            out[name] = m.group(1)
    if "__VIEWSTATE" not in out:
        raise fetch.FetchError("페드워치: __VIEWSTATE 를 찾지 못했다")
    return out


def _action(html: str) -> str:
    m = re.search(r'<form[^>]*action="\.?/?([^"]+)"', html)
    if not m:
        raise fetch.FetchError("페드워치: 폼 주소를 찾지 못했다")
    return HOST + m.group(1).replace("&amp;", "&").lstrip("./")


def _label_date(label: str) -> datetime.date | None:
    """'28 Oct26' -> 2026-10-28."""
    m = _LABEL.search(label)
    if not m or m.group(2) not in _MONTH:
        return None
    try:
        return datetime.date(2000 + int(m.group(3)),
                             _MONTH[m.group(2)], int(m.group(1)))
    except ValueError:
        return None


def _triple(html: str) -> dict | None:
    m = _TRIPLE.search(fetch.plain(html))
    if not m:
        return None
    row = {"cut": float(m.group(1)), "hold": float(m.group(2)),
           "hike": float(m.group(3))}
    return fetch.even_out(row)


def fetch_odds(today: datetime.date | None = None,
               days: int = 100) -> dict:
    today = today or datetime.date.today()
    s = fetch.session()
    s.headers["Referer"] = "https://www.cmegroup.com/"
    first = fetch.get(TOOL, s)

    lv = _LEVEL.search(first)
    level = (f"{int(lv.group(1))/100:.2f}~{int(lv.group(2))/100:.2f}%"
             if lv else None)
    action = _action(first)
    state = _state(first)

    want = []
    for idx, label in _MEETING_BTN.findall(first):
        day = _label_date(fetch.plain(label))
        if day and today <= day <= today + datetime.timedelta(days=days):
            want.append((int(idx), day))

    meetings = []
    for idx, day in want:
        data = dict(state)
        data["__EVENTTARGET"] = _TAB.format(idx=idx)
        try:
            r = s.post(action, data=data, timeout=fetch.TIMEOUT)
            row = _triple(r.text) if r.status_code == 200 else None
        except Exception:
            row = None
        if not row:
            continue
        # 받아 온 쪽이 정말 그 회의인지 확인한다. 되돌림이 어긋나면 앞
        # 회의의 숫자가 그대로 다시 오는데, 그러면 두 줄이 같아진다.
        shown = _TITLE.search(r.text)
        if shown:
            got = shown.group(1).strip()
            if str(day.day) not in got:
                continue
        row["date"] = day.isoformat()
        row["bp"] = None
        meetings.append(row)

    if not meetings:
        raise fetch.FetchError("페드워치: 회의 확률을 하나도 읽지 못했다")
    return {
        "code": "US", "bank": "미국 연준", "rate": "연방기금 목표범위",
        "level": level, "derived": False,
        "source": "CME 페드워치", "url": PUBLIC,
        "meetings": meetings,
    }
