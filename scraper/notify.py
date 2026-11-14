"""텔레그램으로 메시지를 보내는 부분"""
import html
import os

import requests

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
LIMIT = 3800  # 텔레그램 한 메시지 최대 4096자 → 여유 있게


def send(text):
    if not TOKEN or not CHAT_ID:
        print("[텔레그램] 토큰/채팅ID가 없어 전송을 건너뜁니다.\n" + text)
        return
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": "true"},
        timeout=20,
    )
    if not r.ok:
        print("[텔레그램] 전송 실패:", r.status_code, r.text[:300])


def send_new_jobs(jobs, dashboard_url=""):
    """새 공고 목록을 카테고리별로 묶어서 보냅니다. 길면 여러 메시지로 나눕니다."""
    if not jobs:
        return
    order = ["금융권", "전략기획", "기타"]
    icon = {"금융권": "💰", "전략기획": "🧭", "기타": "📌"}
    lines = [f"🔔 <b>새 인턴 공고 {len(jobs)}건</b>"]
    for cat in order:
        group = [j for j in jobs if j["categories"][0] == cat]
        if not group:
            continue
        lines.append(f"\n{icon[cat]} <b>{cat}</b> ({len(group)})")
        for j in group:
            co = f"[{html.escape(j['company'])}] " if j["company"] and j["company"] not in j["title"] else ""
            dl = f" · 마감 {j['deadline']}" if j["deadline"] else ""
            lines.append(f"• {co}<a href=\"{html.escape(j['url'])}\">{html.escape(j['title'])}</a>"
                         f"\n   <i>{html.escape(j['source'])}{dl}</i>")
    if dashboard_url:
        lines.append(f"\n📊 <a href=\"{dashboard_url}\">대시보드 열기</a>")

    buf = ""
    for line in lines:
        if len(buf) + len(line) + 1 > LIMIT:
            send(buf)
            buf = ""
        buf += line + "\n"
    if buf.strip():
        send(buf)
