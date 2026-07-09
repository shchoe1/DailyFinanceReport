"""주요 뉴스 + 경제 이벤트.
- 뉴스: Google News RSS (미국/한국 증시 관련 전일 헤드라인)
- 이벤트: ForexFactory 주간 경제 캘린더 JSON (오늘/내일 미국·한국 주요 일정)
둘 다 무료·헤드리스로 수집 가능.
"""
from __future__ import annotations
import re
import json
import html
import datetime as dt
from datetime import timezone, timedelta
from email.utils import parsedate_to_datetime
import requests
from config import DATA_DIR

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0 Safari/537.36"
KST = timezone(timedelta(hours=9))

GN = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"
NEWS_Q = {
    "US": ("US+stock+market+OR+S%26P+500+OR+Nasdaq", "en-US", "US", "US:en"),
    "KR": ("%EC%BD%94%EC%8A%A4%ED%94%BC+OR+%EC%A6%9D%EC%8B%9C+OR+%EC%BD%94%EC%8A%A4%EB%8B%A5", "ko", "KR", "KR:ko"),
}
FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
IMPACT_RANK = {"High": 3, "Medium": 2, "Low": 1, "Holiday": 0}


def _clean_title(t: str) -> tuple[str, str]:
    t = html.unescape(t).strip()
    # Google News 는 "제목 - 매체명" 형식
    if " - " in t:
        title, src = t.rsplit(" - ", 1)
        return title.strip(), src.strip()
    return t, ""


def _gnews(q: str, hl: str, gl: str, ceid: str, n: int = 3) -> list[dict]:
    url = GN.format(q=q, hl=hl, gl=gl, ceid=ceid)
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
    except Exception:
        return []
    items = re.findall(r"<item>(.*?)</item>", r.text, re.S)
    out, seen = [], set()
    for it in items:
        tm = re.search(r"<title>(.*?)</title>", it, re.S)
        lm = re.search(r"<link>(.*?)</link>", it, re.S)
        pm = re.search(r"<pubDate>(.*?)</pubDate>", it, re.S)
        if not tm:
            continue
        title, src = _clean_title(tm.group(1))
        key = title[:20]
        if not title or key in seen:
            continue
        seen.add(key)
        out.append({"title": title, "source": src,
                    "link": lm.group(1).strip() if lm else "",
                    "pub": pm.group(1).strip() if pm else ""})
        if len(out) >= n:
            break
    return out


def translate_en_ko(text: str) -> str:
    """무료 Google 번역(gtx) — 실패 시 원문 반환."""
    if not text:
        return text
    import urllib.parse
    u = ("https://translate.googleapis.com/translate_a/single?client=gtx"
         "&sl=en&tl=ko&dt=t&q=" + urllib.parse.quote(text))
    try:
        j = requests.get(u, headers={"User-Agent": UA}, timeout=10).json()
        return "".join(seg[0] for seg in j[0] if seg and seg[0])
    except Exception:
        return text


def fetch_news(region: str, n: int = 3) -> list[dict]:
    q, hl, gl, ceid = NEWS_Q[region]
    items = _gnews(q, hl, gl, ceid, n)
    if region == "US":                      # 미국 뉴스는 한글 번역 병기
        for x in items:
            x["title_ko"] = translate_en_ko(x["title"])
    return items


def _is_recent(pub: str, now: dt.datetime, days: int = 4) -> bool:
    try:
        return (now - parsedate_to_datetime(pub)) <= timedelta(days=days)
    except Exception:
        return False


def _event_kst(iso: str) -> dt.datetime | None:
    try:
        d = dt.datetime.fromisoformat(iso)
        return d.astimezone(KST)
    except Exception:
        return None


def _second_thursday(year: int, month: int) -> dt.date:
    d = dt.date(year, month, 1)
    first_thu = d + timedelta(days=(3 - d.weekday()) % 7)  # Thu=3
    return first_thu + timedelta(days=7)


def _kr_expiry_events(today: dt.date, tomorrow: dt.date) -> list[dict]:
    """한국 파생 만기일(매월 둘째 목요일; 3·6·9·12월은 동시만기) 자동 계산."""
    out = []
    for d in (today, tomorrow):
        if d == _second_thursday(d.year, d.month):
            quad = d.month in (3, 6, 9, 12)
            out.append({
                "dt": dt.datetime(d.year, d.month, d.day, 15, 20, tzinfo=KST),
                "date": d.strftime("%m/%d"), "time": "15:20",
                "title": "선물·옵션 동시 만기(쿼드러플위칭)" if quad else "옵션 만기일",
                "impact": "High", "forecast": "", "previous": "", "tag": "만기",
                "soon": True,
            })
    return out


def fetch_events(us_n: int = 3, kr_n: int = 3) -> dict:
    """오늘/내일(KST) 미국·한국 주요 경제 이벤트. 부족하면 이번주 일정/증시일정 뉴스로 보충."""
    cache_path = DATA_DIR / "ff_calendar.json"
    data = []
    try:
        r = requests.get(FF_URL, headers={"User-Agent": UA}, timeout=20)
        if r.status_code == 200:
            data = r.json()
            cache_path.write_text(json.dumps(data), encoding="utf-8")  # 성공분 캐시
        # 429(호출제한) 등은 재시도하지 않고 캐시로 폴백
    except Exception:
        pass
    if not data and cache_path.exists():          # 실패 시 최근 성공 캘린더 재사용
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            data = []

    today = dt.date.today()
    tomorrow = today + timedelta(days=1)

    def collect(country: str, n: int) -> list[dict]:
        rows = []
        for e in data:
            if e.get("country") != country:
                continue
            k = _event_kst(e.get("date", ""))
            if not k:
                continue
            rows.append({
                "dt": k, "date": k.strftime("%m/%d"), "time": k.strftime("%H:%M"),
                "title": e.get("title", ""), "impact": e.get("impact", ""),
                "forecast": e.get("forecast", ""), "previous": e.get("previous", ""),
                "tag": "지표", "soon": k.date() in (today, tomorrow),
            })
        soon = sorted([r for r in rows if r["soon"]],
                      key=lambda x: (-IMPACT_RANK.get(x["impact"], 0), x["dt"]))
        rest = sorted([r for r in rows if not r["soon"]], key=lambda x: x["dt"])
        return soon + rest

    us = collect("USD", us_n)[:us_n]

    # 한국: FF KRW + 만기일 + (부족 시) 증시일정 뉴스
    kr = _kr_expiry_events(today, tomorrow) + collect("KRW", kr_n)
    if len(kr) < kr_n:
        # 폴백: '증시 일정/경제지표 발표' 전용 검색 헤드라인
        sched = _gnews("%EC%A6%9D%EC%8B%9C+%EC%9D%BC%EC%A0%95+OR+%EA%B2%BD%EC%A0%9C%EC%A7%80%ED%91%9C+%EB%B0%9C%ED%91%9C",
                       "ko", "KR", "KR:ko", n=kr_n * 3)
        now = dt.datetime.now(timezone.utc)
        sched = [x for x in sched if _is_recent(x.get("pub", ""), now, days=4)]
        for x in sched:
            kr.append({"dt": None, "date": "", "time": "",
                       "title": x["title"], "impact": "", "forecast": "",
                       "previous": "", "tag": "뉴스", "soon": False,
                       "source": x.get("source", "")})
            if len(kr) >= kr_n:
                break
    kr = kr[:kr_n]

    return {"US": us, "KR": kr, "asof": today.strftime("%Y-%m-%d")}


def fetch_news_and_events() -> dict:
    return {
        "news_us": fetch_news("US"),
        "news_kr": fetch_news("KR"),
        "events": fetch_events(),
    }


if __name__ == "__main__":
    d = fetch_news_and_events()
    for reg in ("news_us", "news_kr"):
        print(f"\n=== {reg} ===")
        for x in d[reg]:
            print(f"  · {x['title']}  ({x['source']})")
    print("\n=== events US ===")
    for e in d["events"]["US"]:
        print(f"  {e['date']} {e['time']} [{e['impact']}] {e['title']} (예상 {e['forecast']}/이전 {e['previous']})")
    print("=== events KR ===")
    for e in d["events"]["KR"]:
        print(f"  {e['date']} {e['time']} [{e['impact']}] {e['title']} (예상 {e['forecast']}/이전 {e['previous']})")
