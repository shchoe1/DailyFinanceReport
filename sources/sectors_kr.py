"""한국 업종별 등락률 — 네이버 금융 (sise_group). 전일 어느 업종이 강했는지 파악용.
파싱 실패 시 빈 리스트를 반환해 리포트가 계속 동작하도록 한다.
"""
from __future__ import annotations
import re
from config import naver_session


def fetch_kr_sectors() -> list[dict]:
    """[{'name': 업종명, 'chg_pct': 등락률}] 등락 순 정렬."""
    s = naver_session()
    url = "https://finance.naver.com/sise/sise_group.naver?type=upjong"
    try:
        r = s.get(url, timeout=15)
        r.encoding = "euc-kr"
    except Exception:
        return []
    html = r.text
    rows = []
    # 각 업종 행: <a href="/sise/sise_group_detail.naver?type=upjong&no=NN">업종명</a> ... 등락률%
    for m in re.finditer(
        r'sise_group_detail\.naver\?type=upjong&no=\d+"[^>]*>([^<]+)</a>.*?'
        r'(<span[^>]*tah[^>]*>|<td[^>]*>)\s*([-+]?\d+\.\d+)%',
        html, re.S):
        name = m.group(1).strip()
        try:
            chg = float(m.group(3))
        except ValueError:
            continue
        rows.append({"name": name, "chg_pct": chg})
    # 폴백: 등락률 셀 위치가 바뀌었을 때 이름만이라도
    if not rows:
        for m in re.finditer(
            r'sise_group_detail\.naver\?type=upjong&no=\d+"[^>]*>([^<]+)</a>', html):
            rows.append({"name": m.group(1).strip(), "chg_pct": 0.0})
    # 이름 중복 제거 + 비정상 등락률(파싱오류) 제거
    seen, uniq = set(), []
    for x in rows:
        if x["name"] in seen:
            continue
        if abs(x["chg_pct"]) > 15:  # 일간 업종 등락 ±15% 초과는 오파싱으로 간주
            x["chg_pct"] = 0.0
        seen.add(x["name"])
        uniq.append(x)
    uniq.sort(key=lambda x: x["chg_pct"], reverse=True)
    return uniq


if __name__ == "__main__":
    secs = fetch_kr_sectors()
    print(f"{len(secs)} sectors")
    for x in secs[:8]:
        print(f"  {x['chg_pct']:+.2f}%  {x['name']}")
    print("  ...")
    for x in secs[-5:]:
        print(f"  {x['chg_pct']:+.2f}%  {x['name']}")
