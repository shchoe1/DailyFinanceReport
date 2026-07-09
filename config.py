"""공용 설정: 경로, HTTP 세션, 상수."""
from __future__ import annotations
import os
from pathlib import Path
import requests
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / "data"
REPORTS_DIR = BASE / "reports"
DATA_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

load_dotenv(BASE / ".env")

# --- 카카오 ---
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "")
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI", "https://localhost:8080")
# 앱에 '클라이언트 시크릿'이 켜져 있으면 필수. 꺼져 있으면 비워두면 됨.
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET", "")
KAKAO_TOKEN_FILE = BASE / "kakao_token.json"

# --- 발송 옵션 ---
# 카카오는 해외 IP(클라우드) 발송이 막히므로 로컬(한국)에서만, 텔레그램은 클라우드에서.
SEND_KAKAO = os.getenv("SEND_KAKAO", "1") == "1"
SEND_TELEGRAM = os.getenv("SEND_TELEGRAM", "0") == "1"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- 리포트 웹 게시(GitHub Pages) — 카톡 '자세히 보기' 링크용 ---
GITHUB_USER = os.getenv("GITHUB_USER", "")     # GitHub 사용자명
GITHUB_REPO = os.getenv("GITHUB_REPO", "")     # 공개 저장소 이름 (예: market-report)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")   # Personal Access Token (contents 쓰기 권한)
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
# GitHub Actions 등 클라우드에서 Pages가 호스팅할 때의 공개 URL 베이스
# 예: https://<user>.github.io/<repo>  (설정 시 git push 대신 이 URL만 사용)
REPORT_BASE_URL = os.getenv("REPORT_BASE_URL", "").rstrip("/")
SITE_DIR = BASE / "site"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


def naver_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": "https://finance.naver.com/sise/"})
    return s


# 미국 섹터 ETF -> (한글 섹터명, 연관 한국 업종/키워드)
US_SECTORS = {
    "XLK":  ("미국 기술",        ["IT", "반도체", "소프트웨어"]),
    "SOXX": ("미국 반도체",      ["반도체", "반도체소재/장비"]),
    "XLC":  ("미국 커뮤니케이션", ["인터넷", "게임", "미디어"]),
    "XLY":  ("미국 임의소비재",  ["자동차", "유통", "화장품"]),
    "XLI":  ("미국 산업재",      ["조선", "기계", "방산"]),
    "XLE":  ("미국 에너지",      ["정유", "화학"]),
    "XLF":  ("미국 금융",        ["은행", "증권", "보험"]),
    "XLV":  ("미국 헬스케어",    ["제약", "바이오"]),
    "XLB":  ("미국 소재",        ["철강", "화학", "2차전지소재"]),
    "XLP":  ("미국 필수소비재",  ["음식료", "필수소비재"]),
    "XLU":  ("미국 유틸리티",    ["전력", "유틸리티"]),
}

# 미국 섹터 -> 한국 대표 업종 영향 매핑 (섹터 임팩트 계산용)
US_TO_KR = {
    "SOXX": ["반도체", "IT부품"],
    "XLK":  ["IT", "소프트웨어"],
    "XLC":  ["인터넷/게임", "미디어"],
    "XLY":  ["자동차", "2차전지"],
    "XLE":  ["정유/화학"],
    "XLF":  ["은행/증권"],
    "XLV":  ["제약/바이오"],
    "XLB":  ["철강/소재"],
}
