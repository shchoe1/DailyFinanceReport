"""오케스트레이터 — 데이터 수집 → 분석 → HTML 저장 → 카카오 발송.
사용:
  python main.py            # 전체 실행(설정 시 카카오 발송)
  python main.py --dry-run  # 발송하지 않고 리포트만 생성
"""
from __future__ import annotations
import os
import sys
import datetime as dt
import traceback

from config import SEND_KAKAO, KAKAO_TOKEN_FILE
from sources.investors import load_and_update
from sources.nasdaq import fetch_nasdaq, fetch_usdkrw
from sources.sectors_kr import fetch_kr_sectors
from sources.liquidity import load_and_update_deposit, deposit_summary
from sources.stocks_kr import kospi_movers
from sources.news import fetch_news_and_events
from analyze import build_analysis
from report import kakao_chunks, save_html


def log(msg: str) -> None:
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


def collect():
    inv = {}
    for mk in ("KOSPI", "KOSDAQ"):
        try:
            inv[mk] = load_and_update(mk)
            log(f"투자자 수급 {mk}: {len(inv[mk])}일")
        except Exception as e:
            log(f"[경고] {mk} 수급 수집 실패: {e}")
            inv[mk] = None
    try:
        nasdaq = fetch_nasdaq()
        log(f"나스닥/섹터: 최근 마감 {nasdaq.get('asof')}")
    except Exception as e:
        log(f"[경고] 나스닥 수집 실패: {e}")
        nasdaq = {"asof": None, "items": {}}
    try:
        krs = fetch_kr_sectors()
        log(f"한국 업종: {len(krs)}개")
    except Exception as e:
        log(f"[경고] 업종 수집 실패: {e}")
        krs = []
    try:
        deposit = deposit_summary(load_and_update_deposit())
        log(f"고객예탁금: {deposit.get('date')} {deposit.get('고객예탁금',0)/10000:,.1f}조 ({deposit.get('trend')})")
    except Exception as e:
        log(f"[경고] 예탁금 수집 실패: {e}")
        deposit = {}
    try:
        fx = fetch_usdkrw()
        log(f"원/달러: {fx.get('level')}원 ({fx.get('chg_1d_pct')}% · {fx.get('won_dir')})")
    except Exception as e:
        log(f"[경고] 환율 수집 실패: {e}")
        fx = {}
    try:
        stocks = kospi_movers()
        log(f"KOSPI 종목: 유니버스 {stocks.get('universe')}개 (상위/중위 10)")
    except Exception as e:
        log(f"[경고] 개별종목 수집 실패: {e}")
        stocks = {}
    try:
        news = fetch_news_and_events()
        ev = news.get("events", {})
        log(f"뉴스: 美 {len(news.get('news_us',[]))}·韓 {len(news.get('news_kr',[]))} / "
            f"이벤트: 美 {len(ev.get('US',[]))}·韓 {len(ev.get('KR',[]))}")
    except Exception as e:
        log(f"[경고] 뉴스·이벤트 수집 실패: {e}")
        news = {}
    return inv, nasdaq, krs, deposit, fx, stocks, news


def main() -> int:
    dry = "--dry-run" in sys.argv
    today = dt.date.today().strftime("%Y-%m-%d")
    log(f"=== 한국증시 수급 브리핑 시작 ({today}) ===")

    inv, nasdaq, krs, deposit, fx, stocks, news = collect()
    if not any(v is not None and not v.empty for v in inv.values()):
        log("[중단] 투자자 수급 데이터가 전혀 없습니다.")
        return 2

    A = build_analysis(inv, nasdaq, krs, deposit, fx, stocks, news)
    path = save_html(A, today)
    log(f"HTML 리포트 저장: {path}")

    # 웹 게시(surge) → 카톡 '자세히 보기' 링크
    report_url = None
    try:
        from publish import publish_report
        report_url = publish_report(path, today)
        log(f"웹 게시: {report_url}" if report_url else "웹 게시: 미설정(로컬만)")
    except Exception as e:
        log(f"[경고] 웹 게시 실패: {e}")

    chunks = kakao_chunks(A, today)
    log(f"카카오 메시지 {len(chunks)}건 생성 (최대 {max(len(c) for c in chunks)}자)")

    if dry:
        log("[--dry-run] 발송 생략.")
        return 0
    if not SEND_KAKAO:
        log("[설정] SEND_KAKAO=0 → 발송 생략.")
        return 0
    if not (KAKAO_TOKEN_FILE.exists() or os.getenv("KAKAO_REFRESH_TOKEN")):
        log("[안내] 토큰 없음 → 로컬은 'python kakao_auth.py', 클라우드는 KAKAO_REFRESH_TOKEN 시크릿 설정. (발송 생략)")
        return 0

    try:
        from kakao import send_messages
        n = send_messages(chunks, link_url=report_url)
        log(f"카카오 발송 완료: {n}건" + (f" (자세히보기 → {report_url})" if report_url else ""))
    except Exception as e:
        log(f"[오류] 카카오 발송 실패: {e}")
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
