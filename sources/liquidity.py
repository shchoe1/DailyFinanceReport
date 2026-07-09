"""증시 자금 동향 — 고객예탁금(투자자예탁금) + 신용잔고. 네이버 금융 증시자금동향.
고객예탁금은 개인의 '매수 대기 자금'으로, 증가 시 개인 매수 여력 확대 신호.
공표가 T+2 지연되므로 '직전 발표치'를 직전일 기준으로 사용한다. 단위: 억원.
"""
from __future__ import annotations
import re
import pandas as pd
from config import naver_session, DATA_DIR


def _to_int(s: str) -> int:
    s = s.replace(",", "").strip()
    return int(s) if re.fullmatch(r"-?\d+", s) else 0


def fetch_deposit() -> pd.DataFrame:
    """columns: date, 고객예탁금(억), 신용잔고(억). 날짜 오름차순."""
    s = naver_session()
    r = s.get("https://finance.naver.com/sise/sise_deposit.naver", timeout=15)
    r.encoding = "euc-kr"
    html = r.text

    tables = re.findall(r"<table[^>]*>(.*?)</table>", html, re.S)
    rows = []
    for tb in tables:
        if "예탁금" not in re.sub(r"<[^>]+>", " ", tb):
            continue
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S):
            cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip()
                     for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            cells = [c for c in cells if c != ""]
            if not cells:
                continue
            m = re.match(r"(\d{2})\.(\d{2})\.(\d{2})", cells[0])
            if not m:
                continue
            date = f"20{m.group(1)}-{m.group(2)}-{m.group(3)}"
            nums = [_to_int(c) for c in cells[1:]]
            if len(nums) < 3:
                continue
            # 열 구성: 고객예탁금(금액,증감), 신용잔고(금액,증감), ...
            rows.append({"date": date, "고객예탁금": nums[0], "신용잔고": nums[2]})
        if rows:
            break

    df = pd.DataFrame(rows).drop_duplicates(subset="date").sort_values("date").reset_index(drop=True)
    return df


def load_and_update_deposit() -> pd.DataFrame:
    fresh = fetch_deposit()
    path = DATA_DIR / "deposit.csv"
    if path.exists() and not fresh.empty:
        try:
            old = pd.read_csv(path)
            fresh = (pd.concat([old, fresh]).drop_duplicates(subset="date", keep="last")
                     .sort_values("date").reset_index(drop=True))
        except Exception:
            pass
    if not fresh.empty:
        fresh.to_csv(path, index=False, encoding="utf-8-sig")
    return fresh


def deposit_summary(df: pd.DataFrame) -> dict:
    """직전일(최신) 고객예탁금 + 전일대비 + 5일 변화."""
    if df is None or df.empty:
        return {}
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else last
    d5 = df.iloc[-6] if len(df) >= 6 else df.iloc[0]
    val = int(last["고객예탁금"])
    chg1 = val - int(prev["고객예탁금"])
    chg5 = val - int(d5["고객예탁금"])
    return {
        "date": last["date"],
        "고객예탁금": val,                 # 억원
        "전일대비": chg1,
        "5일대비": chg5,
        "신용잔고": int(last["신용잔고"]),
        "trend": "증가" if chg1 > 0 else ("감소" if chg1 < 0 else "보합"),
    }


if __name__ == "__main__":
    df = load_and_update_deposit()
    print(f"{len(df)} rows")
    print(df.tail(6).to_string(index=False))
    print("summary:", deposit_summary(df))
