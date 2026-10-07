# -*- coding: utf-8 -*-
"""index.html 을 만든다 — 시장이 보는 정책금리 변경 확률 한 장.

조간 브리핑 맨 아래 '참고자료'에 걸리는 세 번째 쪽이다(차트팩·일정표 다음).
날마다 새로 만든다.

세 곳 다 **남이 계산해 공개한 수치**다. 연준은 CME 가 연방기금 선물로,
ECB·일본은행은 제3자가 €STR·OIS 선물로 낸다. 격이 같지는 않으므로 칸마다
출처를 붙인다 — 거래소와 제3자 모델은 다르다.

한국은행은 2026-10-06 에 뺐다(소장님 지시). 공개 확률 지표가 없어 통안증권
91일 금리에서 역산했는데, 관측 하나로 회의 여럿을 푸는 것이라 다른 셋과
격이 달랐다. 셈법은 git 이력의 `build/bokcurve.py` 에 남아 있다.

한 곳이 실패하면 그 칸만 빠지고 나머지는 올라간다. 빠진 것은 화면에 적는다.
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import cbwatch                                                # noqa: E402
import fedwatch                                               # noqa: E402
import fetch
import jscheck                                         # noqa: E402                                                  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "template.html"
OUTPUT = ROOT / "index.html"

WEEKDAY = "월화수목금토일"
WINDOW = 100          # 앞으로 볼 날 수. 대개 회의 두 번이 들어온다.


def log(msg: str = "") -> None:
    print(msg, flush=True)


def esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def collect(today: datetime.date) -> tuple[list[dict], list[str]]:
    jobs = (
        ("연준", lambda: fedwatch.fetch_odds(today, WINDOW)),
        ("ECB", lambda: cbwatch.fetch_odds("EA", today, WINDOW)),
        ("일본은행", lambda: cbwatch.fetch_odds("JP", today, WINDOW)),
    )
    out, warn = [], []
    for name, fn in jobs:
        try:
            got = fn()
        except Exception as exc:        # noqa: BLE001 — 한 곳이 통째로 막혀도
            warn.append(f"{name} 확률을 받지 못했다 — {exc}")   # 나머지는 올린다
            log(f"  [실패] {name} — {type(exc).__name__} {exc}")
            continue
        out.append(got)
        log(f"  {name:6} 회의 {len(got['meetings'])}건 "
            f"(현재 {got['level']}) {got['source']}")
    return out, warn


def bar(row: dict) -> str:
    """인하·동결·인상 띠. 너무 얇은 칸에는 숫자를 넣지 않는다."""
    bits = []
    for key, cls in (("cut", "c"), ("hold", "h"), ("hike", "k")):
        v = row[key]
        if v <= 0:
            continue
        label = f"{v:.0f}" if v >= 12 else ""
        bits.append(f'<span class="{cls}" style="width:{v:.4f}%">{label}</span>')
    return f'<div class="bar">{"".join(bits)}</div>'


def meeting_row(row: dict) -> str:
    day = datetime.date.fromisoformat(row["date"])
    bp = (f'{row["bp"]:+.0f}bp' if row.get("bp") is not None else "")
    return (
        f'<div class="mtg">'
        f'<span class="d">{day.month}.{day.day}'
        f'<span style="font-weight:400;color:var(--muted)">'
        f'({WEEKDAY[day.weekday()]})</span></span>'
        f'{bar(row)}'
        f'<span class="nums">'
        f'<span class="c">인하 {row["cut"]:.1f}</span>'
        f'<span>동결 {row["hold"]:.1f}</span>'
        f'<span class="k">인상 {row["hike"]:.1f}</span></span>'
        f'<span class="bp">{bp}</span>'
        f'</div>')


def bank_block(b: dict) -> str:
    """한 중앙은행 묶음. '공개 수치' 띠를 셋 다 달고 간다.

    이 쪽에 내가 계산한 숫자는 없다는 뜻이다. 한국은행을 뺀 뒤로는 셋이
    모두 같은 띠라 군더더기처럼 보이지만, 남겨 둔다 — 읽는 사람이 '이것도
    누가 셈한 건가' 를 묻지 않게 하는 것이 이 쪽의 요체다.
    """
    rows = "".join(meeting_row(r) for r in b["meetings"])
    return (
        f'<section class="bank">'
        f'<h2>{esc(b["bank"])}'
        f'<span class="lv">{esc(b["rate"])} {esc(b["level"] or "?")}</span></h2>'
        f'<div class="src"><span class="badge">공개 수치</span>'
        f'<a href="{esc(b["url"])}" target="_blank" rel="noopener">'
        f'{esc(b["source"])}</a></div>'
        f'{rows}</section>')


NOTE = """<b>무엇을 보여 주나</b> 각 통화정책회의 시점에 정책금리가 오늘보다
낮을(인하)·같을(동결)·높을(인상) 확률입니다. 셋을 더하면 100 입니다.
앞으로 약 석 달 안의 회의만 싣습니다.
<br><br>
<b>세 곳 다 남이 계산해 공개한 수치입니다.</b> 이 쪽에서 제가 계산한 숫자는
없습니다. 다만 격이 같지는 않습니다.
<ul>
<li><b>연준</b> — CME 페드워치. 연방기금 선물로 <b>거래소가</b> 계산해
공개한 것을 그대로 옮깁니다.</li>
<li><b>ECB·일본은행</b> — Central Bank Watch. €STR·OIS 선물로 계산해 날마다
공개합니다. CME 의 €STRWatch 는 유료로 막혀 있어 이쪽을 씁니다.
<b>중앙은행도 거래소도 아닌 제3자 모델</b>이라는 점을 감안해 주십시오.</li>
</ul>
<b>한국은행은 싣지 않습니다.</b> 공신력 있는 공개 확률 지표가 없습니다.
통안증권 91일 금리에서 역산해 한동안 실었으나, 관측 하나로 회의 여럿을
푸는 것이라 <b>어느 회의 몫인지를 가릴 수 없고</b> 위 셋과 격이 달랐습니다.
같은 표에 나란히 두면 같은 무게로 읽히므로 뺐습니다(2026년 10월).
<br><br>
<b>블룸버그 WIRP 를 쓰지 않는 까닭</b> 공신력은 높지만 날마다 손으로 받아야
해 자동 갱신에 맞지 않습니다. 예측시장(폴리마켓 등)도 쓰지 않습니다 —
선물 기반만큼 공신력이 없습니다."""


def ops_blob(today, banks, warn) -> str:
    ops = {
        "built": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%MZ"),
        "asOf": today.isoformat(),
        "banks": [b["code"] for b in banks],
        "warn": [" ".join(w.split()) for w in warn],
        "rows": [{"code": b["code"], "d": r["date"], "cut": r["cut"],
                  "hold": r["hold"], "hike": r["hike"], "bp": r.get("bp")}
                 for b in banks for r in b["meetings"]],
    }
    return json.dumps(ops, ensure_ascii=False).replace("<", "\\u003c")


def build(today: datetime.date) -> str:
    log(f"확률 수집 — {today} 기준, 앞으로 {WINDOW}일")
    banks, warn = collect(today)
    if not banks:
        raise fetch.FetchError("세 곳 모두 받지 못했다 — 쪽을 쓰지 않는다")

    stamp = (f'{today.year}년 {today.month}월 {today.day}일 '
             f'({WEEKDAY[today.weekday()]}) 기준')
    warn_html = ""
    if warn:
        warn_html = ('<div class="warn"><b>일부를 받지 못했습니다.</b> '
                     + " / ".join(esc(w) for w in warn) + '</div>')

    page = TEMPLATE.read_text(encoding="utf-8")
    page = page.replace("__STAMP__", stamp)
    page = page.replace("__WARN__", warn_html)
    page = page.replace("__BANKS__", "\n".join(bank_block(b) for b in banks))
    page = page.replace("__NOTE__", NOTE)
    page = page.replace("__OPS__", ops_blob(today, banks, warn))
    log(f"\n중앙은행 {len(banks)}곳, 회의 "
        f"{sum(len(b['meetings']) for b in banks)}건")
    return page


def main() -> int:
    ap = argparse.ArgumentParser(description="정책금리 변경 확률 페이지")
    ap.add_argument("--check", action="store_true", help="쓰지 않고 만들어만 본다")
    ap.add_argument("--date", help="기준일을 바꿔 본다 (YYYY-MM-DD)")
    args = ap.parse_args()

    today = (datetime.date.fromisoformat(args.date) if args.date
             else datetime.date.today())
    page = build(today)
    # 쪽을 쓰기 전에 자바스크립트가 성한지 본다. 깨졌으면 여기서 멈춘다 —
    # 깨진 쪽을 올리느니 어제 쪽이 그대로 떠 있는 편이 낫다(2026-10-07).
    jscheck.must_be_sound(page, log)
    if args.check:
        log("--check: 파일을 쓰지 않았다.")
        return 0
    OUTPUT.write_text(page, encoding="utf-8")
    log(f"index.html 갱신 — {len(page):,}자")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
