# 시장이 보는 정책금리 변경 확률

<https://tskang89.github.io/policy-odds/>

조간 브리핑 맨 아래 '참고자료'에 걸리는 쪽이다. 차트팩·일정표와 같은 꼴로
만들었고, 평일 새벽에 새로 만든다.

네 중앙은행(연준·ECB·일본은행·한국은행)의 앞으로 약 석 달 안 회의마다,
**그 시점에 정책금리가 오늘보다 낮을·같을·높을 확률**을 싣는다. 셋의 합은
100 이다. 그 회의에서 새로 움직일 확률이 아니다 — 뒤 회의 칸에는 앞 회의에서
움직일 가능성이 이미 들어 있으므로 칸끼리 더하면 안 된다.

## 출처가 넷으로 갈린다

| | 출처 | 격 |
|---|---|---|
| 연준 | CME 페드워치 | 거래소가 선물로 계산해 공개 |
| ECB | Central Bank Watch | 제3자가 €STR·OIS 선물로 계산해 공개 |
| 일본은행 | Central Bank Watch | 〃 |
| 한국은행 | ECOS 단기금리에서 **역산** | 내가 계산 |

CME 가 €STRWatch 를 유료로 돌려 ECB 를 그쪽에서 받을 수 없다("You do not
have access to this feature", 2026-10-05 확인). 한국은행은 공신력 있는 공개
확률 지표가 없다.

`www.cmegroup.com` 은 Akamai 가 코드 접속을 막는다(403). 페드워치 도구 자체는
`cmegroup-tools.quikstrike.net` 에 올라가 있고 그쪽은 막혀 있지 않다.

## 한국은행 역산

만기 T 일 금리를 그 사이 하루짜리 금리의 평균으로 보고, 금리가 회의 때마다
25bp 계단으로 움직인다고 가정해 회의 시점의 반영 변화폭을 푼다. 그 변화폭을
25bp 한 칸으로 선형으로 나누어 확률로 바꾼다 — +7.5bp 면 인상 30 · 동결 70.

통안증권에는 기간 프리미엄이 섞여 있어 인상 쪽으로 치우치고, 둘째 회의는
'그 뒤로는 더 움직이지 않는다'는 가정이 들어가 더 거칠다. 그래서 반영
변화폭(bp)을 화면에 함께 적는다.

## 돌리기

```
pip install -r requirements.txt
ECOS_API_KEY=... python build/make.py          # index.html 을 새로 쓴다
ECOS_API_KEY=... python build/make.py --check  # 쓰지 않고 만들어만 본다
```

`ECOS_API_KEY` 는 저장소 비밀값(Settings → Secrets)에 둔다. 한국은행 쪽만
쓰므로, 없으면 한국은행 칸만 빠지고 나머지 셋은 올라간다.

## 짜임

```
build/fetch.py      공통 받아오기 · 확률 합을 100 으로 맞추기
build/fedwatch.py   연준 (QuikStrike 되돌림으로 회의를 넘겨 가며 읽는다)
build/cbwatch.py    ECB·일본은행 (쪽에 심긴 분포 JSON 을 읽는다)
build/bokcurve.py   한국은행 (ECOS + 회의일 + 역산)
build/make.py       쪽 만들기
template.html       틀
```

한 곳이 실패해도 나머지는 올라가고, 빠진 것은 화면에 적는다. 네 곳이 다
실패하면 쪽을 쓰지 않는다 — 빈 쪽을 올리면 '시장이 아무것도 안 보고 있다'로
읽힌다.
