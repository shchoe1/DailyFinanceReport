"""분석 엔진 — 투자자 수급 신호, 당일 방향/규모 휴리스틱 예측,
나스닥→한국 섹터 영향 매핑, 기관/개인/연기금 리밸런싱 압력 추정.

※ 모든 '예측'은 공개 데이터 기반의 확률적 휴리스틱이며 적중을 보장하지 않는다.
   과최적화를 피하기 위해 규칙은 단순·투명하게 유지한다.
"""
from __future__ import annotations
import pandas as pd
from config import US_TO_KR

INVESTORS = ["외국인", "기관계", "개인", "연기금"]


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _center(score: float, avg_mag: float) -> int:
    """방향점수(score≈[-1.6,1.6])와 평소 거래규모로 당일 순매수 중심값(억) 추정."""
    sign = 1 if score > 0 else (-1 if score < 0 else 0)
    return int(round(sign * min(1.0, abs(score) / 1.6) * (avg_mag or 1000)))


# ---------- 기본 통계 ----------
def _streak(vals: list[int]) -> int:
    """최근값 기준 연속 순매수(+)/순매도(-) 일수. 부호 포함."""
    if not vals:
        return 0
    sign = 1 if vals[-1] > 0 else (-1 if vals[-1] < 0 else 0)
    if sign == 0:
        return 0
    n = 0
    for v in reversed(vals):
        if (v > 0 and sign > 0) or (v < 0 and sign < 0):
            n += 1
        else:
            break
    return n * sign


def flow_stats(df: pd.DataFrame, col: str) -> dict:
    vals = df[col].tolist()
    last = vals[-1] if vals else 0
    s5 = sum(vals[-5:])
    s20 = sum(vals[-20:])
    mag = pd.Series([abs(v) for v in vals[-20:]])
    return {
        "last": int(last),
        "sum5": int(s5),
        "sum20": int(s20),
        "streak": _streak(vals),
        "avg_mag": float(mag.mean()) if len(mag) else 0.0,
        "std_mag": float(mag.std(ddof=0)) if len(mag) else 0.0,
    }


# ---------- 미국 시황 리스크 톤 ----------
def us_risk_tone(nasdaq: dict) -> dict:
    it = nasdaq["items"]
    ixic = it.get("^IXIC", {}).get("chg_pct", 0.0)
    sox = it.get("^SOX", {}).get("chg_pct", 0.0)
    vix = it.get("^VIX", {}).get("chg_pct", 0.0)
    krw = it.get("KRW=X", {}).get("chg_pct", 0.0)   # +면 원화 약세
    tnx = it.get("^TNX", {}).get("chg_pct", 0.0)
    # 위험선호 점수: 나스닥·반도체 강세 + VIX 하락 + 원화 강세(krw<0)
    score = 0.5 * ixic + 0.4 * sox - 0.15 * vix - 0.6 * krw
    if score > 0.5:
        tone = "위험선호(Risk-on)"
    elif score < -0.5:
        tone = "위험회피(Risk-off)"
    else:
        tone = "중립"
    return {"ixic": ixic, "sox": sox, "vix": vix, "krw": krw, "tnx": tnx,
            "score": round(score, 2), "tone": tone}


# ---------- 규모 버킷 ----------
def _scale_bucket(est_abs: float, stats: dict) -> str:
    avg = stats["avg_mag"] or 1.0
    if est_abs >= 1.6 * avg:
        return "대량"
    if est_abs >= 0.6 * avg:
        return "보통"
    return "소량"


def _fmt_range(center: int, spread: int) -> str:
    def r100(x):
        return int(round(x / 100.0)) * 100
    lo, hi = r100(center - spread), r100(center + spread)
    return f"{lo:+,}~{hi:+,}억"


# ---------- 투자자별 당일 예측 ----------
def predict_flows(df: pd.DataFrame, tone: dict, deposit: dict | None = None,
                  fx: dict | None = None) -> dict:
    """외국인/기관/개인/연기금 각각의 당일 방향·규모 휴리스틱 예측.
    deposit(고객예탁금)·fx(원/달러) 직전일 데이터를 예측 입력으로 반영한다."""
    st = {c: flow_stats(df, c) for c in INVESTORS}
    out = {}

    # 외국인: 미국 위험선호(나스닥·반도체·원화)와 최근 추세의 결합
    f = st["외국인"]
    macro = _clamp(tone["score"], -2, 2)          # 위험선호 점수(클램프)
    trend = 1 if f["streak"] > 0 else (-1 if f["streak"] < 0 else 0)
    mom5 = _clamp(f["sum5"] / ((f["avg_mag"] or 1000) * 5), -1.5, 1.5)  # 5일 모멘텀 정규화
    fscore = 0.5 * macro + 0.3 * trend + 0.3 * mom5   # 대략 [-1.6, 1.6]
    fdir = "매수" if fscore > 0.3 else ("매도" if fscore < -0.3 else "중립")
    conf = min(0.85, 0.4 + abs(fscore) * 0.25)
    center = _center(fscore, f["avg_mag"])
    out["외국인"] = {
        "dir": fdir, "conf": round(conf, 2),
        "scale": _scale_bucket(abs(center), f),
        "est_range": _fmt_range(center, int((f["std_mag"] or f["avg_mag"] or 1000) * 0.45)),
        "reasons": [
            f"美 시황 {tone['tone']} (나스닥 {tone['ixic']:+.1f}%, 반도체 {tone['sox']:+.1f}%)",
            (f"원/달러 {fx['level']:,.1f}원 (전일 {fx['chg_1d_won']:+.1f}원 {fx['chg_1d_pct']:+.2f}%, "
             f"5일 {fx['chg_5d_pct']:+.2f}%) → 원화 {fx['won_dir']}"
             f"{'(외국인 우호)' if fx['won_dir']=='강세' else '(비우호)' if fx['won_dir']=='약세' else ''}")
            if fx else
            f"원/달러 {tone['krw']:+.1f}% → 원화 {'약세(비우호)' if tone['krw']>0 else '강세(우호)'}",
            f"직전일({df['date'].iloc[-1]}) 외국인 실제 {f['last']:+,}억 · "
            f"{abs(f['streak'])}일 연속 {'순매수' if f['streak']>0 else '순매도' if f['streak']<0 else '혼조'}"
            f", 5일 누적 {f['sum5']:+,}억",
        ],
        "stats": f,
    }

    # 개인: 통상 외국인+기관의 반대편(수급 균형). 고객예탁금(매수대기자금)을 여력 지표로 반영.
    p = st["개인"]
    opp = -(1 if fscore > 0 else -1 if fscore < 0 else 0)
    pconf = 0.55
    p_reasons = [
        "개인은 통상 외국인·기관과 반대 방향으로 수급 균형을 맞추는 경향",
        f"직전일({df['date'].iloc[-1]}) 개인 실제 {p['last']:+,}억 · "
        f"{abs(p['streak'])}일 연속 {'순매수' if p['streak']>0 else '순매도' if p['streak']<0 else '혼조'}"
        f", 5일 누적 {p['sum5']:+,}억",
    ]
    if deposit:
        cap = deposit["trend"]
        p_reasons.append(
            f"고객예탁금 {deposit['고객예탁금']/10000:,.1f}조 ({cap}, 전일 {deposit['전일대비']:+,}억 · "
            f"5일 {deposit['5일대비']:+,}억) → 개인 매수여력 {'확대' if cap=='증가' else '축소' if cap=='감소' else '보합'}")
        # 예탁금 방향이 예측 방향과 일치하면 신뢰도 소폭 가산, 상충하면 감산
        if (cap == "증가" and opp > 0) or (cap == "감소" and opp < 0):
            pconf += 0.07
        elif (cap == "증가" and opp < 0) or (cap == "감소" and opp > 0):
            pconf -= 0.07
    pdir = "매수" if opp > 0 else ("매도" if opp < 0 else "중립")
    pcenter = _center(opp * min(1.0, abs(fscore)), p["avg_mag"])
    out["개인"] = {
        "dir": pdir, "conf": round(pconf, 2),
        "scale": _scale_bucket(abs(pcenter), p),
        "est_range": _fmt_range(pcenter, int((p["std_mag"] or p["avg_mag"] or 1000) * 0.45)),
        "reasons": p_reasons,
        "stats": p,
    }

    # 기관계: 외국인과 부분 역상관 + 자체 추세
    inst = st["기관계"]
    iscore = -0.4 * fscore + 0.5 * (1 if inst["streak"] > 0 else -1 if inst["streak"] < 0 else 0)
    idir = "매수" if iscore > 0.3 else ("매도" if iscore < -0.3 else "중립")
    icenter = _center(iscore, inst["avg_mag"])
    out["기관계"] = {
        "dir": idir, "conf": 0.5,
        "scale": _scale_bucket(abs(icenter), inst),
        "est_range": _fmt_range(icenter, int((inst["std_mag"] or inst["avg_mag"] or 1000) * 0.45)),
        "reasons": [
            "기관은 외국인 수급의 반대편 + 자체 포지션 조정 성격",
            f"직전일({df['date'].iloc[-1]}) 기관 실제 {inst['last']:+,}억 · "
            f"{abs(inst['streak'])}일 연속 {'순매수' if inst['streak']>0 else '순매도' if inst['streak']<0 else '혼조'}"
            f", 5일 누적 {inst['sum5']:+,}억",
        ],
        "stats": inst,
    }

    return out


# ---------- 연기금 리밸런싱 압력 ----------
def rebalancing_pressure(df: pd.DataFrame) -> dict:
    """연기금·기관의 자산배분 리밸런싱 성격 압력 추정.
    최근 20일 누적 순매수가 한 방향으로 과도하면, 목표비중 회귀(반대 매매) 압력이 커진다는 가정.
    """
    pen = flow_stats(df, "연기금")
    inst = flow_stats(df, "기관계")

    def pressure(stats, label):
        s20 = stats["sum20"]
        avg = stats["avg_mag"] or 1.0
        z = s20 / (avg * 5 + 1e-9)   # 20일 누적을 정규화
        if z > 1.2:
            return f"{label}: 최근 20일 누적 순매수 {s20:+,}억으로 과매수 → 차익·리밸런싱 매도 압력"
        if z < -1.2:
            return f"{label}: 최근 20일 누적 순매도 {s20:+,}억으로 과매도 → 비중복구 매수 압력"
        return f"{label}: 20일 누적 {s20:+,}억, 리밸런싱 압력 중립"

    return {
        "연기금": pressure(pen, "연기금"),
        "기관계": pressure(inst, "기관계"),
        "raw": {"연기금": pen, "기관계": inst},
    }


# ---------- 나스닥 → 한국 섹터 영향 ----------
# 미국 섹터별 한국 전이 계수(베타). 반도체는 상관이 가장 높다.
BETA = {"SOXX": 0.75, "XLK": 0.55, "XLC": 0.45, "XLY": 0.4,
        "XLE": 0.35, "XLF": 0.3, "XLV": 0.3, "XLB": 0.4}


def sector_impact(nasdaq: dict) -> list[dict]:
    it = nasdaq["items"]
    agg: dict[str, dict] = {}
    for etf, kr_list in US_TO_KR.items():
        us = it.get(etf)
        if not us:
            continue
        exp = us["chg_pct"] * BETA.get(etf, 0.4)
        for kr in kr_list:
            a = agg.setdefault(kr, {"kr_sector": kr, "score": 0.0, "drivers": []})
            a["score"] += exp
            a["drivers"].append(f"{us['name']} {us['chg_pct']:+.1f}%")
    rows = list(agg.values())
    for r in rows:
        r["score"] = round(r["score"], 2)
        r["direction"] = "▲" if r["score"] > 0.1 else ("▼" if r["score"] < -0.1 else "―")
    rows.sort(key=lambda x: x["score"], reverse=True)
    return rows


# ---------- 종합 ----------
MAJOR_INDICES = [("^IXIC", "나스닥종합"), ("^GSPC", "S&P500"), ("^DJI", "다우"),
                 ("^SOX", "필라델피아반도체"), ("^VIX", "VIX 변동성"),
                 ("^TNX", "미국채10년"), ("DX-Y.NYB", "달러인덱스"), ("KRW=X", "원/달러")]


def us_major_indices(nasdaq: dict) -> list[dict]:
    out = []
    for key, name in MAJOR_INDICES:
        it = nasdaq["items"].get(key)
        if it:
            out.append({"name": name, "close": it["close"],
                        "chg_pct": it["chg_pct"], "date": it["date"]})
    return out


def build_analysis(inv: dict[str, pd.DataFrame], nasdaq: dict, kr_sectors: list,
                   deposit: dict | None = None, fx: dict | None = None,
                   stocks: dict | None = None, news: dict | None = None) -> dict:
    tone = us_risk_tone(nasdaq)
    markets = {}
    for mk, df in inv.items():
        if df is None or df.empty:
            continue
        markets[mk] = {
            "latest_date": df["date"].iloc[-1],
            "rows": len(df),
            "predictions": predict_flows(df, tone, deposit, fx),
            "rebalancing": rebalancing_pressure(df),
        }
    impact = sector_impact(nasdaq)
    kr_top = [s for s in kr_sectors if s["chg_pct"] != 0][:5]
    kr_bot = [s for s in kr_sectors if s["chg_pct"] != 0][-5:]
    return {
        "us_tone": tone,
        "us_asof": nasdaq.get("asof"),
        "us_indices": us_major_indices(nasdaq),
        "fx": fx or {},
        "deposit": deposit or {},
        "markets": markets,
        "sector_impact": impact,
        "kr_sector_top": kr_top,
        "kr_sector_bottom": kr_bot,
        "kospi_stocks": stocks or {},
        "news": news or {},
    }
