"""카카오 '나에게 보내기' — refresh token으로 access token 갱신 후 텍스트 메모 발송.
토큰은 kakao_token.json 에 저장/갱신된다.
"""
from __future__ import annotations
import os
import json
import time
import datetime as dt
import requests
from config import KAKAO_REST_API_KEY, KAKAO_CLIENT_SECRET, KAKAO_TOKEN_FILE, BASE

AUTH_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
# 클라우드(GitHub Actions)에서 새 refresh_token 을 시크릿에 반영하기 위한 출력 파일
ROTATED_RT_FILE = BASE / "kakao_refresh_token.txt"


def load_token() -> dict:
    """로컬은 kakao_token.json, 클라우드는 KAKAO_REFRESH_TOKEN 환경변수에서 로드."""
    if KAKAO_TOKEN_FILE.exists():
        return json.loads(KAKAO_TOKEN_FILE.read_text(encoding="utf-8"))
    rt = os.getenv("KAKAO_REFRESH_TOKEN", "")
    if rt:
        return {"refresh_token": rt}          # access_token 은 곧바로 갱신됨
    raise FileNotFoundError(
        "토큰이 없습니다. 로컬은 'python kakao_auth.py', 클라우드는 KAKAO_REFRESH_TOKEN 시크릿을 설정하세요.")


def save_token(tok: dict) -> None:
    try:
        KAKAO_TOKEN_FILE.write_text(json.dumps(tok, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
    except Exception:
        pass                                   # 클라우드 임시 파일시스템에서 실패해도 무시


def refresh_access_token(tok: dict) -> dict:
    """refresh_token 으로 새 access_token 발급. 새 refresh_token 이 오면 함께 저장·기록."""
    data = {
        "grant_type": "refresh_token",
        "client_id": KAKAO_REST_API_KEY,
        "refresh_token": tok["refresh_token"],
    }
    if KAKAO_CLIENT_SECRET:
        data["client_secret"] = KAKAO_CLIENT_SECRET
    r = requests.post(AUTH_TOKEN_URL, data=data, timeout=15)
    r.raise_for_status()
    j = r.json()
    tok["access_token"] = j["access_token"]
    tok["expires_in"] = j.get("expires_in", 21600)
    tok["obtained_at"] = time.time()
    if j.get("refresh_token"):                # 갱신 임박 시에만 새로 내려줌
        tok["refresh_token"] = j["refresh_token"]
        try:                                   # 클라우드: 시크릿 회전용으로 기록
            ROTATED_RT_FILE.write_text(j["refresh_token"], encoding="utf-8")
        except Exception:
            pass
    save_token(tok)
    return tok


def _valid_access(tok: dict) -> bool:
    if "access_token" not in tok or "obtained_at" not in tok:
        return False
    age = time.time() - tok["obtained_at"]
    return age < (tok.get("expires_in", 21600) - 300)   # 만료 5분 전 갱신


def get_access_token() -> str:
    tok = load_token()
    if not _valid_access(tok):
        tok = refresh_access_token(tok)
    return tok["access_token"]


def send_text(text: str, link_url: str | None = None) -> None:
    access = get_access_token()
    # ⚠️ 카카오는 메시지 링크 도메인을 '등록된 Web 플랫폼 사이트 도메인'으로 제한한다.
    #    m.stock.naver.com 을 앱 > 플랫폼(Web)에 등록해야 이 링크가 정상 동작한다.
    default_link = "https://m.stock.naver.com/domestic/index/KOSPI/total"
    template = {"object_type": "text", "text": text[:2000],
                "link": {"web_url": link_url or default_link,
                         "mobile_web_url": link_url or default_link}}
    r = requests.post(MEMO_URL,
                      headers={"Authorization": f"Bearer {access}"},
                      data={"template_object": json.dumps(template, ensure_ascii=False)},
                      timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"카카오 발송 실패 {r.status_code}: {r.text}")
    # 카카오는 성공 시 {"result_code":0}. 200이어도 result_code!=0 이면 미전달.
    try:
        body = r.json()
    except ValueError:
        body = {}
    print(f"[kakao] status=200 result_code={body.get('result_code')} body={r.text[:200]}",
          flush=True)
    if body.get("result_code", 0) != 0:
        raise RuntimeError(f"카카오 미전달 result_code={body.get('result_code')}: {r.text}")


def send_messages(messages: list[str], gap_sec: float = 0.6,
                  link_url: str | None = None) -> int:
    sent = 0
    for m in messages:
        send_text(m, link_url=link_url)
        sent += 1
        time.sleep(gap_sec)
    return sent


if __name__ == "__main__":
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    send_text(f"✅ 카카오 발송 테스트 ({now})\n한국증시 수급 브리핑 봇이 정상 연결되었습니다.")
    print("테스트 메시지 발송 완료 — 카카오톡을 확인하세요.")
