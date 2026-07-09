"""텔레그램 chat_id 찾기 — 봇에게 먼저 아무 메시지나 보낸 뒤 실행하면 chat_id를 알려준다.
사용: .env 에 TELEGRAM_BOT_TOKEN 만 넣고  python telegram_setup.py
"""
from __future__ import annotations
import requests
from config import TELEGRAM_BOT_TOKEN


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        print("[오류] .env 의 TELEGRAM_BOT_TOKEN 이 비어 있습니다.")
        return
    r = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates", timeout=15)
    data = r.json()
    if not data.get("ok"):
        print("[오류] 봇 토큰이 올바르지 않습니다:", data)
        return
    chats = {}
    for u in data.get("result", []):
        msg = u.get("message") or u.get("channel_post") or {}
        chat = msg.get("chat") or {}
        if chat.get("id"):
            chats[chat["id"]] = chat.get("title") or chat.get("username") or chat.get("first_name") or ""
    if not chats:
        print("최근 메시지가 없습니다. 텔레그램에서 봇에게 아무 메시지나(예: 'hi') 먼저 보낸 뒤 다시 실행하세요.")
        return
    print("발견된 chat_id (이 값을 .env / GitHub 시크릿의 TELEGRAM_CHAT_ID 에 넣으세요):")
    for cid, name in chats.items():
        print(f"  TELEGRAM_CHAT_ID = {cid}   ({name})")


if __name__ == "__main__":
    main()
