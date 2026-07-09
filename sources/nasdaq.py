"""나스닥 전일 시황 + 미국 섹터 ETF + 환율/금리 — yfinance.
한국장 아침 실행 시, 미국 '가장 최근 마감 세션'의 등락을 계산한다.
"""
from __future__ import annotations
import yfinance as yf
import pandas as pd
from config import US_SECTORS

TICKERS = {
    "^IXIC": "나스닥종합",
    "^GSPC": "S&P500",
    "^DJI":  "다우",
    "^SOX":  "필라델피아반도체",
    "^VIX":  "VIX(변동성)",
    "^TNX":  "미국채10년",
    "DX-Y.NYB": "달러인덱스",
    "KRW=X": "원/달러",
}
TICKERS.update({k: v[0] for k, v in US_SECTORS.items()})


def _last_two_valid(series: pd.Series):
    s = series.dropna()
    if len(s) < 2:
        return None, None, None
    prev, last = s.iloc[-2], s.iloc[-1]
    date = s.index[-1].strftime("%Y-%m-%d")
    return last, (last / prev - 1) * 100, date


def fetch_nasdaq() -> dict:
    tickers = list(TICKERS.keys())
    raw = yf.download(tickers, period="10d", interval="1d",
                      progress=False, auto_adjust=True, threads=False)
    close = raw["Close"]
    out = {"asof": None, "items": {}}
    for t in tickers:
        if t not in close.columns:
            continue
        last, chg, date = _last_two_valid(close[t])
        if last is None:
            continue
        out["items"][t] = {"name": TICKERS[t], "close": round(float(last), 2),
                           "chg_pct": round(float(chg), 2), "date": date}
        if t == "^IXIC":
            out["asof"] = date
    return out


def fetch_usdkrw() -> dict:
    """원/달러 직전일 기준 상세: 레벨, 전일대비, 5일대비, 최근 5일 종가.
    +등락%면 원화 약세(외국인 비우호), -면 원화 강세(우호)."""
    raw = yf.download("KRW=X", period="10d", interval="1d",
                      progress=False, auto_adjust=True, threads=False)
    s = raw["Close"]
    if hasattr(s, "columns"):        # 단일 티커도 DataFrame로 올 때 대비
        s = s.iloc[:, 0]
    s = s.dropna()
    if len(s) < 2:
        return {}
    last = float(s.iloc[-1])
    prev = float(s.iloc[-2])
    base5 = float(s.iloc[-6]) if len(s) >= 6 else float(s.iloc[0])
    recent = [round(float(x), 1) for x in s.tail(5).tolist()]
    return {
        "date": s.index[-1].strftime("%Y-%m-%d"),
        "level": round(last, 1),
        "chg_1d_pct": round((last / prev - 1) * 100, 2),
        "chg_1d_won": round(last - prev, 1),
        "chg_5d_pct": round((last / base5 - 1) * 100, 2),
        "recent": recent,
        "won_dir": "약세" if last > prev else ("강세" if last < prev else "보합"),
    }


def us_sector_moves(nasdaq: dict) -> list[tuple[str, str, float]]:
    """(etf, 한글명, 등락%) 리스트를 등락 순으로."""
    rows = []
    for etf in US_SECTORS:
        it = nasdaq["items"].get(etf)
        if it:
            rows.append((etf, it["name"], it["chg_pct"]))
    rows.sort(key=lambda x: x[2], reverse=True)
    return rows


if __name__ == "__main__":
    d = fetch_nasdaq()
    print("as of (last US session):", d["asof"])
    for t, it in d["items"].items():
        print(f"  {it['name']:12s} {it['close']:>10.2f}  {it['chg_pct']:+.2f}%  ({it['date']})")
