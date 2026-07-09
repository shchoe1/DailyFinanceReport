"""카카오 최초 1회 인증 — authorization code 를 받아 access/refresh 토큰을 저장한다.

사전 준비 (developers.kakao.com):
  1) 애플리케이션 추가 → [앱 키]의 'REST API 키' 를 .env 의 KAKAO_REST_API_KEY 에 입력
  2) [카카오 로그인] 활성화 ON
  3) [카카오 로그인] > Redirect URI 에 .env 의 KAKAO_REDIRECT_URI 와 '동일하게' 등록
     (기본값: https://localhost:8080)
  4) [카카오 로그인] > 동의항목 > '카카오톡 메시지 전송(talk_message)' 사용 설정
그 후:  python kakao_auth.py  실행 → 안내에 따라 진행
"""
from __future__ import annotations
import sys
import time
import webbrowser
import urllib.parse
import requests
from config import KAKAO_REST_API_KEY, KAKAO_REDIRECT_URI, KAKAO_CLIENT_SECRET
from kakao import save_token, AUTH_TOKEN_URL


def build_auth_url() -> str:
    q = urllib.parse.urlencode({
        "client_id": KAKAO_REST_API_KEY,
        "redirect_uri": KAKAO_REDIRECT_URI,
        "response_type": "code",
        "scope": "talk_message",
    })
    return f"https://kauth.kakao.com/oauth/authorize?{q}"


def main() -> None:
    if not KAKAO_REST_API_KEY:
        print("[오류] .env 의 KAKAO_REST_API_KEY 가 비어 있습니다.")
        sys.exit(1)

    url = build_auth_url()
    print("\n[1] 아래 주소를 브라우저에서 열고 카카오 로그인·동의를 진행하세요.")
    print("    (브라우저가 자동으로 열립니다)\n")
    print(url, "\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass

    print("[2] 동의 후 브라우저가 이동한 주소가 다음과 같습니다:")
    print(f"    {KAKAO_REDIRECT_URI}?code=XXXXXXXX  (페이지가 안 열려도 정상)")
    print("    그 주소창의 code 값(또는 전체 주소)을 붙여넣으세요.\n")
    raw = input("code 또는 리다이렉트 주소 입력: ").strip()

    if "code=" in raw:
        code = urllib.parse.parse_qs(urllib.parse.urlparse(raw).query).get("code", [""])[0]
    else:
        code = raw
    if not code:
        print("[오류] code 를 확인하지 못했습니다.")
        sys.exit(1)

    data = {
        "grant_type": "authorization_code",
        "client_id": KAKAO_REST_API_KEY,
        "redirect_uri": KAKAO_REDIRECT_URI,
        "code": code,
    }
    if KAKAO_CLIENT_SECRET:
        data["client_secret"] = KAKAO_CLIENT_SECRET
    r = requests.post(AUTH_TOKEN_URL, data=data, timeout=15)
    if r.status_code != 200:
        print(f"[오류] 토큰 발급 실패 {r.status_code}: {r.text}")
        sys.exit(1)

    j = r.json()
    tok = {
        "access_token": j["access_token"],
        "refresh_token": j["refresh_token"],
        "expires_in": j.get("expires_in", 21600),
        "obtained_at": time.time(),
    }
    save_token(tok)
    print("\n[완료] kakao_token.json 저장됨. 테스트 메시지를 보냅니다...")

    from kakao import send_text
    send_text("✅ 카카오 연결 완료 — 한국증시 수급 브리핑 봇이 준비되었습니다.")
    print("카카오톡에서 테스트 메시지를 확인하세요. 이제 매일 자동 발송이 가능합니다.")


if __name__ == "__main__":
    main()
