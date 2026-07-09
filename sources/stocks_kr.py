"""KOSPI 개별 종목 등락 — 네이버 시가총액 상위 페이지.
시총 상위 유니버스(대형주)를 주가 등락률로 정렬해 상위/중위 종목을 제공.
삼성전자(005930)·SK하이닉스(000660)는 항상 포함.
"""
from __future__ import annotations
import re
import datetime as dt
from config import naver_session

WATCH = {"005930": "삼성전자", "000660": "SK하이닉스"}
ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
LINK_RE = re.compile(r'/item/main\.naver\?code=(\d+)"[^>]*class="tltle">([^<]+)</a>')
CHG_RE = re.compile(r'class="tah p11 (red|nv)\d\d"[^>]*>\s*([-+]?[\d.]+)\s*%')
NUM_RE = re.compile(r'<td class="number">([\d,]+)</td>')


def _parse_page(html: str) -> list[dict]:
    out = []
    for tr in ROW_RE.findall(html):
        lm = LINK_RE.search(tr)
        if not lm:
            continue
        code, name = lm.group(1), lm.group(2).strip()
        cm = CHG_RE.search(tr)
        if not cm:
            continue
        chg = float(cm.group(2).lstrip("+")) * (-1 if cm.group(1) == "nv" else 1)
        nums = NUM_RE.findall(tr)
        price = int(nums[0].replace(",", "")) if nums else 0
        mcap = int(nums[2].replace(",", "")) if len(nums) > 2 else 0   # 억원
        out.append({"code": code, "name": name, "chg": chg,
                    "price": price, "mcap": mcap})
    return out


def fetch_kospi_universe(pages: int = 2) -> list[dict]:
    """KOSPI 시총 상위 유니버스 (기본 2페이지 = 상위 100종목)."""
    s = naver_session()
    rows: list[dict] = []
    for p in range(1, pages + 1):
        r = s.get(f"https://finance.naver.com/sise/sise_market_sum.naver?sosok=0&page={p}",
                  timeout=15)
        r.encoding = "euc-kr"
        rows.extend(_parse_page(r.text))
    # 중복 제거(코드 기준)
    seen, uniq = set(), []
    for x in rows:
        if x["code"] in seen:
            continue
        seen.add(x["code"])
        uniq.append(x)
    return uniq


def attach_prev_trend(stocks: list[dict]) -> None:
    """표시 종목들에 전전날 등락률(chg_prev)을 부착 — pykrx OHLCV(네이버 기반) 사용.
    직전일 등락(chg)은 네이버 시총 페이지값을 그대로 쓰고, 하루 전(전전날) 등락만 계산.
    """
    from pykrx import stock as _stock
    today = dt.date.today()
    frm = (today - dt.timedelta(days=12)).strftime("%Y%m%d")
    to = today.strftime("%Y%m%d")
    cache: dict[str, float | None] = {}
    for s in stocks:
        code = s["code"]
        if code not in cache:
            cache[code] = None
            try:
                df = _stock.get_market_ohlcv_by_date(frm, to, code)
                closes = (df["종가"] if "종가" in df.columns else df.iloc[:, 3]).tolist()
                if len(closes) >= 3 and closes[-3]:
                    cache[code] = round((closes[-2] / closes[-3] - 1) * 100, 2)
            except Exception:
                cache[code] = None
        s["chg_prev"] = cache[code]


def kospi_movers(pages: int = 2) -> dict:
    """등락률 정렬 → 상위 10 / 중위 10 + 관심종목(삼성전자·SK하이닉스)."""
    uni = fetch_kospi_universe(pages)
    if not uni:
        return {"universe": 0, "top": [], "mid": [], "watch": []}
    ranked = sorted(uni, key=lambda x: x["chg"], reverse=True)
    n = len(ranked)
    top = ranked[:10]
    mid_start = max(0, n // 2 - 5)
    mid = ranked[mid_start:mid_start + 10]
    watch = []
    for code, nm in WATCH.items():
        hit = next((x for x in ranked if x["code"] == code), None)
        if hit:
            rank = ranked.index(hit) + 1
            watch.append({**hit, "rank": rank})
    # 표시되는 종목에만 전전날 추이 부착(개별 dict 객체 기준)
    try:
        attach_prev_trend(top + mid + watch)
    except Exception:
        pass
    return {"universe": n, "top": top, "mid": mid, "watch": watch,
            "mid_rank": (mid_start + 1, mid_start + len(mid))}


if __name__ == "__main__":
    m = kospi_movers()
    print(f"universe={m['universe']}  중위구간 순위 {m['mid_rank']}")
    print("--- 관심종목 ---")
    for x in m["watch"]:
        print(f"  {x['rank']:>3}위 {x['name']} {x['chg']:+.2f}% (시총 {x['mcap']/10000:,.0f}조)")
    print("--- 상승 상위 10 ---")
    for x in m["top"]:
        print(f"  {x['name']} {x['chg']:+.2f}% (시총 {x['mcap']/10000:,.0f}조)")
    print("--- 중위 10 ---")
    for x in m["mid"]:
        print(f"  {x['name']} {x['chg']:+.2f}% (시총 {x['mcap']/10000:,.0f}조)")
