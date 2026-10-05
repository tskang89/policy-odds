# -*- coding: utf-8 -*-
"""공통 받아오기. 일정표 저장소의 _get 과 같은 꼴로 둔다.

한 군데라도 실패하면 그 중앙은행만 빠지고 나머지는 올라간다. 통째로
실패하는 것보다 낫지만, 무엇이 빠졌는지는 화면에 적어야 한다 — 빠진 것을
말하지 않으면 '시장이 아무것도 안 보고 있다'로 읽힌다.
"""

from __future__ import annotations

import re
import time

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
TIMEOUT = 40
RETRIES = 3


class FetchError(RuntimeError):
    pass


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA,
                      "Accept-Language": "en-US,en;q=0.9",
                      "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"})
    return s


def get(url: str, s: requests.Session | None = None,
        tries: int = RETRIES, **kw) -> str:
    s = s or session()
    last = None
    for attempt in range(tries):
        try:
            r = s.get(url, timeout=TIMEOUT, **kw)
        except requests.RequestException as exc:
            last = exc
        else:
            if r.status_code == 200:
                r.encoding = r.apparent_encoding or r.encoding
                return r.text
            last = f"HTTP {r.status_code}"
        if attempt + 1 < tries:
            time.sleep(2 * (attempt + 1))
    raise FetchError(f"{url.split('/')[2]}: {last}")


def plain(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


# --------------------------------------------------------------- 확률 환산
def split_bars(bars: list[tuple[int, float]]) -> dict:
    """(오늘 대비 bp, 확률) 목록을 인하·동결·인상 셋으로 묶는다.

    세 값의 합이 100 이 되어야 한다. 원자료가 99.97 처럼 올 때가 있어
    동결 쪽에 나머지를 얹는다 — 가장 큰 칸에 얹으면 눈에 덜 띈다.
    """
    cut = sum(p for bp, p in bars if bp < 0)
    hold = sum(p for bp, p in bars if bp == 0)
    hike = sum(p for bp, p in bars if bp > 0)
    total = cut + hold + hike
    if total <= 0:
        raise FetchError("확률 합이 0 이다")
    cut, hold, hike = (100 * x / total for x in (cut, hold, hike))
    return {"cut": round(cut, 1), "hold": round(hold, 1),
            "hike": round(hike, 1)}


def even_out(row: dict) -> dict:
    """반올림 때문에 합이 100.1 이나 99.9 가 되는 것을 바로잡는다."""
    gap = round(100.0 - (row["cut"] + row["hold"] + row["hike"]), 1)
    if gap:
        big = max(("cut", "hold", "hike"), key=lambda k: row[k])
        row[big] = round(row[big] + gap, 1)
    return row
