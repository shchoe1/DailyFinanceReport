"""리포트 생성 — 상세 HTML(로컬 저장) + 카카오 '나에게 보내기'용 200자 이하 메시지 청크."""
from __future__ import annotations
import datetime as dt
from config import REPORTS_DIR

ARROW = {"매수": "🟢매수", "매도": "🔴매도", "중립": "⚪중립"}


def _f(n: int) -> str:
    return f"{n:+,}"


# ---------- 카카오 메시지(요약) ----------
def kakao_chunks(A: dict, today: str, gen_at: str | None = None) -> list[str]:
    """카카오 텍스트 템플릿(최대 200자) 제한에 맞춘 2~3개 메시지."""
    tone = A["us_tone"]
    fx = A.get("fx") or {}
    dep = A.get("deposit") or {}
    msgs = []

    # 1) 헤드라인 + 미국 시황
    head = (f"📈 한국증시 수급 브리핑\n🕕 {gen_at or today} 생성\n"
            f"[美 전일] 나스닥 {tone['ixic']:+.1f}% · 반도체 {tone['sox']:+.1f}%\n"
            f"→ {tone['tone']}")
    msgs.append(head[:200])

    # 2) 코스피 투자자별 예측
    for mk in ("KOSPI", "KOSDAQ"):
        m = A["markets"].get(mk)
        if not m:
            continue
        p = m["predictions"]
        line = (f"[{mk}] 당일 수급 예측\n"
                f"외국인 {ARROW[p['외국인']['dir']]}({p['외국인']['scale']}) {p['외국인']['est_range']}\n"
                f"기관 {ARROW[p['기관계']['dir']]}({p['기관계']['scale']})\n"
                f"개인 {ARROW[p['개인']['dir']]}({p['개인']['scale']})")
        msgs.append(line[:200])

    # 2.5) 직전일 매크로 — 원/달러 + 고객예탁금
    macro = "[직전일 매크로]"
    if fx:
        macro += (f"\n원/달러 {fx['level']:,.0f}원 (전일 {fx['chg_1d_won']:+.1f}원 "
                  f"{fx['chg_1d_pct']:+.2f}%, 원화 {fx['won_dir']})")
    if dep:
        macro += (f"\n고객예탁금 {dep['고객예탁금']/10000:,.1f}조 ({dep['trend']}, "
                  f"전일 {dep['전일대비']:+,}억)")
    if fx or dep:
        msgs.append(macro[:200])

    # 3) 섹터 영향 + 리밸런싱
    imp = A["sector_impact"][:3]
    imp_s = " ".join(f"{r['kr_sector']}{r['direction']}" for r in imp)
    reb = A["markets"].get("KOSPI", {}).get("rebalancing", {})
    reb_pen = reb.get("연기금", "")
    tail = (f"[섹터 영향(美→韓)] {imp_s}\n"
            f"[리밸런싱] {reb_pen.split(':',1)[-1].strip() if reb_pen else '-'}")
    msgs.append(tail[:200])

    # 3.5) KOSPI 개별종목 — 관심종목 + 상승 상위
    stk = A.get("kospi_stocks") or {}
    if stk.get("top"):
        w = " ".join(f"{x['name']} {x['chg']:+.1f}%({x['rank']}위)" for x in stk.get("watch", []))
        tops = " ".join(f"{x['name']} {x['chg']:+.1f}%" for x in stk["top"][:3])
        smsg = f"[KOSPI 종목]\n{w}\n🔺상승상위 {tops}"
        msgs.append(smsg[:200])

    # 3.7) 주요 뉴스 & 이벤트
    n = A.get("news") or {}
    if n:
        us = n.get("news_us") or []
        kr = n.get("news_kr") or []
        if us:
            u = us[0]
            us_line = f"{u.get('title_ko') or u['title']}\n({u['title']})"
            msgs.append((f"[美 전일뉴스]\n{us_line}")[:200])
        if kr:
            msgs.append((f"[韓 전일뉴스]\n· " + "\n· ".join(x["title"] for x in kr[:2]))[:200])
        ev = n.get("events", {})
        def evline(items):
            return " / ".join(f"{e['title']}" for e in items[:2]) if items else "-"
        emsg = (f"[오늘·내일 이벤트]\n🇺🇸 {evline(ev.get('US'))}\n🇰🇷 {evline(ev.get('KR'))}")
        msgs.append(emsg[:200])

    msgs.append("※ 확률적 휴리스틱 추정치이며 투자 권유가 아닙니다. 이 메시지들이 오늘의 브리핑 전문입니다.")
    return msgs


# ---------- 상세 HTML ----------
def _pred_rows(preds: dict) -> str:
    order = ["외국인", "기관계", "개인"]
    tr = ""
    for k in order:
        p = preds[k]
        color = {"매수": "#e11", "매도": "#06c", "중립": "#777"}[p["dir"]]
        reasons = "<br>".join("· " + r for r in p["reasons"])
        last = p.get("stats", {}).get("last", 0)
        last_c = "#e11" if last > 0 else ("#06c" if last < 0 else "#777")
        tr += (f"<tr><td><b>{k}</b></td>"
               f"<td style='color:{last_c}'>{last:+,}</td>"
               f"<td style='color:{color};font-weight:700'>{p['dir']}</td>"
               f"<td>{p['scale']}</td><td>{p['est_range']}</td>"
               f"<td>{int(p['conf']*100)}%</td>"
               f"<td class='reason'>{reasons}</td></tr>")
    return tr


def _macro_block(A: dict) -> str:
    fx = A.get("fx") or {}
    dep = A.get("deposit") or {}
    if not fx and not dep:
        return ""
    fx_html = ""
    if fx:
        arrow = "▲" if fx["chg_1d_won"] > 0 else ("▼" if fx["chg_1d_won"] < 0 else "―")
        favor = ("외국인 우호" if fx["won_dir"] == "강세"
                 else "외국인 비우호" if fx["won_dir"] == "약세" else "중립")
        trail = " → ".join(f"{x:,.0f}" for x in fx["recent"])
        fx_html = f"""
        <div><b>원/달러 환율</b> <span class="sub">직전일 {fx['date']}</span><br>
         <span style="font-size:20px;font-weight:700">{fx['level']:,.1f}원</span> {arrow}
         전일대비 {fx['chg_1d_won']:+.1f}원 ({fx['chg_1d_pct']:+.2f}%) · 5일 {fx['chg_5d_pct']:+.2f}%<br>
         원화 <b>{fx['won_dir']}</b> ({favor})<br>
         <span class="sub">최근 5일: {trail}</span></div>"""
    dep_html = ""
    if dep:
        arrow = "▲" if dep["전일대비"] > 0 else ("▼" if dep["전일대비"] < 0 else "―")
        cap = ("개인 매수여력 확대" if dep["trend"] == "증가"
               else "개인 매수여력 축소" if dep["trend"] == "감소" else "보합")
        dep_html = f"""
        <div><b>고객예탁금</b> <span class="sub">직전일 {dep['date']} (T+2 공표)</span><br>
         <span style="font-size:20px;font-weight:700">{dep['고객예탁금']/10000:,.1f}조원</span> {arrow}
         전일 {dep['전일대비']:+,}억 · 5일 {dep['5일대비']:+,}억<br>
         <b>{dep['trend']}</b> → {cap}<br>
         <span class="sub">신용잔고 {dep['신용잔고']/10000:,.1f}조원</span></div>"""
    return f"""
    <h2>직전일 매크로·수급환경</h2>
    <div class="cols">{fx_html}{dep_html}</div>"""


def _indices_table(A: dict) -> str:
    idx = A.get("us_indices") or []
    if not idx:
        return ""
    cells = ""
    for it in idx:
        c = "#e11" if it["chg_pct"] > 0 else ("#06c" if it["chg_pct"] < 0 else "#777")
        cells += (f"<tr><td style='text-align:left'><b>{it['name']}</b></td>"
                  f"<td>{it['close']:,.2f}</td>"
                  f"<td style='color:{c};font-weight:700'>{it['chg_pct']:+.2f}%</td></tr>")
    return f"""
    <h2>미국 전일 주요 지수 <span class="sub">최근 마감 {A.get('us_asof') or '-'}</span></h2>
    <table class="grid"><tr><th>지수</th><th>종가</th><th>등락률</th></tr>{cells}</table>"""


def _arrow(pct) -> str:
    if pct is None:
        return "<span style='color:#aaa'>·</span>"
    if pct > 0:
        return "<span style='color:#e11'>▲</span>"
    if pct < 0:
        return "<span style='color:#06c'>▼</span>"
    return "<span style='color:#777'>―</span>"


def _trend_cell(x: dict) -> str:
    """전전날 → 직전일 화살표 추이."""
    prev, last = x.get("chg_prev"), x.get("chg")
    pv = f"{prev:+.1f}" if prev is not None else "-"
    lv = f"{last:+.1f}" if last is not None else "-"
    return (f"<td style='white-space:nowrap'>{_arrow(prev)}<span class='sub'> {pv}</span> "
            f"→ {_arrow(last)}<span class='sub'> {lv}</span></td>")


def _stock_row(x: dict, rank: bool = False) -> str:
    c = "#e11" if x["chg"] > 0 else ("#06c" if x["chg"] < 0 else "#777")
    name = f"<b>{x['name']}</b>"
    if rank and x.get("rank"):
        name += f" <span class='sub'>{x['rank']}위</span>"
    return (f"<tr><td style='text-align:left'>{name}</td>"
            f"{_trend_cell(x)}"
            f"<td style='color:{c};font-weight:700'>{x['chg']:+.2f}%</td>"
            f"<td>{x['price']:,}</td><td>{x['mcap']/10000:,.0f}조</td></tr>")


def _stocks_block(A: dict) -> str:
    s = A.get("kospi_stocks") or {}
    if not s or not s.get("top"):
        return ""
    hdr = ("<tr><th>종목</th><th>2일 추이<br><span class='sub'>전전날→직전일</span></th>"
           "<th>직전일 등락</th><th>현재가</th><th>시총</th></tr>")
    watch = "".join(_stock_row(x, rank=True) for x in s.get("watch", []))
    mr = s.get("mid_rank", (0, 0))
    return f"""
    <h2>KOSPI 개별 종목 등락 <span class="sub">시총 상위 {s.get('universe',0)}종목 중 · 주가 등락률순</span></h2>
    <div class="sub" style="margin:2px 0 6px">▲상승 ▼하락 · 화살표 왼쪽=전전날, 오른쪽=직전일</div>
    <table class="grid">{hdr}{watch}</table>
    <div class="cols">
      <div><b>🔺 상승률 상위 10</b>
        <table class="grid">{hdr}{''.join(_stock_row(x) for x in s['top'])}</table></div>
      <div><b>중위 10</b> <span class="sub">({mr[0]}~{mr[1]}위)</span>
        <table class="grid">{hdr}{''.join(_stock_row(x) for x in s['mid'])}</table></div>
    </div>"""


def _news_block(A: dict) -> str:
    n = A.get("news") or {}
    if not n:
        return ""
    def news_ul(items):
        if not items:
            return "<li class='sub'>수집된 뉴스 없음</li>"
        li = ""
        for x in items:
            src = f" <span class='sub'>({x['source']})</span>" if x.get("source") else ""
            link = x.get("link") or "#"
            # 미국 뉴스는 한글 번역 + 원문(영어) 병기
            if x.get("title_ko"):
                headline = (f"{x['title_ko']} "
                            f"<span class='sub'>({x['title']})</span>")
            else:
                headline = x["title"]
            li += f"<li><a href='{link}' target='_blank'>{headline}</a>{src}</li>"
        return li

    def event_ul(items):
        if not items:
            return "<li class='sub'>예정 이벤트 없음</li>"
        li = ""
        badge = {"High": "🔴", "Medium": "🟠", "Low": "🟡"}
        for e in items:
            b = badge.get(e.get("impact", ""), "🔹" if e.get("tag") == "만기" else "📰")
            when = f"{e['date']} {e['time']}".strip()
            when = f"<span class='sub'>{when}</span> " if when.strip() else ""
            extra = ""
            if e.get("forecast") or e.get("previous"):
                extra = f" <span class='sub'>(예상 {e.get('forecast') or '-'}/이전 {e.get('previous') or '-'})</span>"
            li += f"<li>{b} {when}{e['title']}{extra}</li>"
        return li

    ev = n.get("events", {})
    return f"""
    <h2>📰 주요 뉴스 &amp; 이벤트</h2>
    <div class="cols">
      <div><b>🇺🇸 미국 전일 주요 뉴스</b><ul>{news_ul(n.get('news_us'))}</ul></div>
      <div><b>🇰🇷 한국 전일 주요 뉴스</b><ul>{news_ul(n.get('news_kr'))}</ul></div>
    </div>
    <div class="cols">
      <div><b>🇺🇸 미국 오늘·내일 이벤트</b><ul>{event_ul(ev.get('US'))}</ul></div>
      <div><b>🇰🇷 한국 오늘·내일 이벤트</b><ul>{event_ul(ev.get('KR'))}</ul></div>
    </div>
    <div class="sub">🔴High 🟠Medium 🟡Low 영향도 · 시각은 KST</div>"""


def build_html(A: dict, today: str, gen_at: str | None = None) -> str:
    gen_at = gen_at or today
    tone = A["us_tone"]
    # 미국 섹터
    us_rows = ""
    imp_rows = ""
    for r in A["sector_impact"]:
        drv = ", ".join(dict.fromkeys(r["drivers"]))
        imp_rows += (f"<tr><td>{r['direction']} <b>{r['kr_sector']}</b></td>"
                     f"<td>{r['score']:+.2f}</td><td class='reason'>{drv}</td></tr>")

    market_blocks = ""
    for mk in ("KOSPI", "KOSDAQ"):
        m = A["markets"].get(mk)
        if not m:
            continue
        reb = m["rebalancing"]
        market_blocks += f"""
        <h2>{mk} <span class="sub">기준일 {m['latest_date']} · 이력 {m['rows']}일</span></h2>
        <table class="grid">
          <tr><th>투자자</th><th>직전일 실제(억)</th><th>당일 방향</th><th>규모</th><th>추정 순매수(억)</th><th>신뢰도</th><th>근거</th></tr>
          {_pred_rows(m['predictions'])}
        </table>
        <div class="reb">
          <b>리밸런싱·수급조절 압력</b><br>
          · {reb['연기금']}<br>· {reb['기관계']}
        </div>
        """

    kr_top = "".join(f"<li>{s['chg_pct']:+.2f}% {s['name']}</li>" for s in A["kr_sector_top"])
    kr_bot = "".join(f"<li>{s['chg_pct']:+.2f}% {s['name']}</li>" for s in A["kr_sector_bottom"])

    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{gen_at} · 한국증시 수급 브리핑</title>
<style>
 body{{font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;max-width:860px;margin:0 auto;padding:18px;color:#1a1a1a;background:#fafafa}}
 h1{{font-size:22px;margin:.2em 0}} h2{{font-size:18px;margin-top:1.4em;border-left:4px solid #2b6;padding-left:8px}}
 .sub{{font-size:12px;color:#888;font-weight:400}}
 .tone{{padding:10px 14px;border-radius:8px;background:#eef6ff;margin:10px 0;font-size:15px}}
 table{{border-collapse:collapse;width:100%;margin:8px 0;font-size:13px;background:#fff}}
 th,td{{border:1px solid #e2e2e2;padding:6px 8px;text-align:center;vertical-align:top}}
 td.reason{{text-align:left;color:#555;font-size:12px}}
 .reb{{background:#fff8e6;border:1px solid #f0e0a0;border-radius:8px;padding:10px;font-size:13px;margin:6px 0}}
 .cols{{display:flex;gap:16px;flex-wrap:wrap}} .cols>div{{flex:1;min-width:240px}}
 ul{{margin:.3em 0;padding-left:18px;font-size:13px}}
 .disc{{color:#999;font-size:11px;margin-top:20px;border-top:1px solid #ddd;padding-top:10px}}
</style></head><body>
<h1>📈 {gen_at} 한국증시 수급 브리핑</h1>
<div class="tone">
 <b>미국 전일 시황 (최근 마감 {A.get('us_asof') or '-'})</b><br>
 나스닥 <b>{tone['ixic']:+.2f}%</b> · S&amp;P/필반 반도체 <b>{tone['sox']:+.2f}%</b> ·
 VIX {tone['vix']:+.1f}% · 美10년물 {tone['tnx']:+.1f}% · 원/달러 <b>{tone['krw']:+.2f}%</b><br>
 종합 리스크 톤: <b>{tone['tone']}</b> (점수 {tone['score']})
</div>

{_indices_table(A)}

{_macro_block(A)}

{_news_block(A)}

{market_blocks}

<h2>나스닥 → 한국 섹터 영향 (전이계수 반영)</h2>
<table class="grid"><tr><th>한국 섹터(예상)</th><th>영향점수</th><th>미국측 동인</th></tr>{imp_rows}</table>

<h2>전일 한국 업종 등락 (참고)</h2>
<div class="cols">
 <div><b>강세 상위</b><ul>{kr_top}</ul></div>
 <div><b>약세 하위</b><ul>{kr_bot}</ul></div>
</div>

{_stocks_block(A)}

<div class="disc">
 ⚠️ 본 리포트는 KRX 대체(네이버 금융)·yfinance 공개데이터 기반의 <b>확률적 휴리스틱 추정</b>입니다.
 외국인·기관·개인의 실제 당일 매매를 보장하지 않으며, 투자 판단의 책임은 이용자 본인에게 있습니다.
 생성: {gen_at} (자동)
</div>
</body></html>"""


def save_html(A: dict, today: str, gen_at: str | None = None) -> str:
    html = build_html(A, today, gen_at)
    path = REPORTS_DIR / f"report_{today}.html"
    path.write_text(html, encoding="utf-8")
    return str(path)
