"""텔레그램 발송 — 봇 API. 해외(GitHub 클라우드) IP에서도 정상 동작한다.
설정: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID.
카톡 청크들을 4096자 제한에 맞춰 몇 개의 메시지로 합쳐 보낸다.
"""
from __future__ import annotations
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

API = "https://api.telegram.org/bot{token}/sendMessage"
LIMIT = 3500   # 텔레그램 4096 제한 여유


def _pack(chunks: list[str], link_url: str | None) -> list[str]:
    """여러 카톡 청크를 구분선으로 이어 붙여 3500자 이하 메시지들로 재편성."""
    tail = f"\n\n📄 상세 리포트: {link_url}" if link_url else ""
    msgs, cur = [], ""
    for c in chunks:
        block = c + "\n\n━━━━━━━━\n"
        if len(cur) + len(block) > LIMIT:
            msgs.append(cur.rstrip("\n━ "))
            cur = ""
        cur += block
    if cur:
        msgs.append(cur.rstrip("\n━ "))
    if msgs and tail:
        if len(msgs[-1]) + len(tail) <= 4096:
            msgs[-1] += tail
        else:
            msgs.append(tail.strip())
    return msgs


def send_telegram(chunks: list[str], link_url: str | None = None) -> int:
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        raise RuntimeError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 미설정")
    url = API.format(token=TELEGRAM_BOT_TOKEN)
    sent = 0
    for text in _pack(chunks, link_url):
        r = requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "disable_web_page_preview": "true",
        }, timeout=15)
        if r.status_code != 200:
            raise RuntimeError(f"텔레그램 발송 실패 {r.status_code}: {r.text[:200]}")
        sent += 1
    return sent


if __name__ == "__main__":
    n = send_telegram(["✅ 텔레그램 연결 테스트", "한국증시 수급 브리핑 봇이 정상 연결되었습니다."],
                      link_url="https://example.com")
    print(f"텔레그램 {n}건 발송 완료 — 텔레그램을 확인하세요.")
