"""투자자별 매매동향 (개인/외국인/기관) — 네이버 금융에서 수집.
KRX data.krx.co.kr 은 Akamai 봇 차단으로 프로그램 접근 불가하여 네이버로 우회.
단위: 억원 (순매수 기준, +매수우위 / -매도우위).
"""
from __future__ import annotations
import re
import datetime as dt
import pandas as pd
from config import naver_session, DATA_DIR

SOSOK = {"KOSPI": "01", "KOSDAQ": "02"}
NUM_RE = re.compile(r"-?[\d,]+")


def _to_int(s: str) -> int:
    s = s.replace(",", "").strip()
    if not s or s in {"-", "+"}:
        return 0
    try:
        return int(s)
    except ValueError:
        return 0


def _parse_date(token: str) -> str | None:
    # "26.07.08" -> "2026-07-08"
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{2})", token)
    if m:
        yy, mm, dd = m.groups()
        return f"20{yy}-{mm}-{dd}"
    m = re.match(r"(\d{4})\.(\d{2})\.(\d{2})", token)
    if m:
        return "-".join(m.groups())
    return None


def fetch_investor_trend(market: str) -> pd.DataFrame:
    """최근 약 20영업일 투자자별 순매수(억원) 시계열.
    columns: date, 개인, 외국인, 기관계, 연기금, 기타법인
    """
    sosok = SOSOK[market]
    s = naver_session()
    bizdate = dt.date.today().strftime("%Y%m%d")
    url = (f"https://finance.naver.com/sise/investorDealTrendDay.naver"
           f"?bizdate={bizdate}&sosok={sosok}&page=1")
    r = s.get(url, timeout=15)
    r.encoding = "euc-kr"
    html = r.text

    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if not cells:
            continue
        text_cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        date = _parse_date(text_cells[0])
        if not date:
            continue
        nums = [_to_int(c) for c in text_cells[1:] if NUM_RE.fullmatch(c.replace(",", "").replace("+", "")) or c.replace(",", "").lstrip("-+").isdigit()]
        # 관대한 재추출: 날짜 이후 셀에서 숫자만
        nums = []
        for c in text_cells[1:]:
            m = NUM_RE.search(c)
            nums.append(_to_int(m.group()) if m else 0)
        if len(nums) < 3:
            continue
        row = {
            "date": date,
            "개인": nums[0],
            "외국인": nums[1],
            "기관계": nums[2],
            "연기금": nums[8] if len(nums) > 9 else (nums[-2] if len(nums) >= 5 else 0),
            "기타법인": nums[-1] if len(nums) >= 4 else 0,
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.drop_duplicates(subset="date").sort_values("date").reset_index(drop=True)
    return df


def load_and_update(market: str) -> pd.DataFrame:
    """네이버에서 최신치를 받아 로컬 history(csv)와 병합·저장 후 반환."""
    fresh = fetch_investor_trend(market)
    path = DATA_DIR / f"investors_{market}.csv"
    if path.exists():
        try:
            old = pd.read_csv(path)
            merged = pd.concat([old, fresh]).drop_duplicates(subset="date", keep="last")
            merged = merged.sort_values("date").reset_index(drop=True)
        except Exception:
            merged = fresh
    else:
        merged = fresh
    if not merged.empty:
        merged.to_csv(path, index=False, encoding="utf-8-sig")
    return merged


if __name__ == "__main__":
    for mk in ("KOSPI", "KOSDAQ"):
        df = load_and_update(mk)
        print(f"\n=== {mk} ({len(df)} rows) ===")
        print(df.tail(6).to_string(index=False))
