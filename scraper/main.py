"""
전체 흐름을 실행하는 파일입니다.  (실행:  python scraper/main.py)

  ① 모든 사이트에서 공고 수집
  ② 직무 분류 (금융권 / 전략기획 / 기타)
  ③ 예전에 본 공고와 비교해서 '새 공고'만 골라냄
  ④ docs/data.json 저장 → 대시보드가 이 파일을 읽음
  ⑤ 새 공고를 텔레그램으로 전송
"""
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from classify import classify, is_intern  # noqa: E402
from notify import send, send_new_jobs  # noqa: E402
from sources import KST, SOURCES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "docs" / "data.json"     # 대시보드용 데이터
SEEN_FILE = ROOT / "data" / "seen.json"     # 이미 알림 보낸 공고 ID 목록

# 텔레그램 알림 범위:  "focus" = 금융권·전략기획만,  "all" = 모든 새 공고
NOTIFY_MODE = os.environ.get("NOTIFY_MODE", "focus")
NOTIFY_INTERN_ONLY = os.environ.get("NOTIFY_INTERN_ONLY", "true") == "true"
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "")
KEEP_DAYS = 21          # 목록에서 사라진 뒤 며칠까지 대시보드에 남겨둘지
FAIL_ALERT_AFTER = 3    # 같은 사이트가 연속 몇 번 실패하면 텔레그램으로 알려줄지


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def norm_key(job):
    """여러 사이트에 똑같이 올라온 공고를 하나로 묶기 위한 키"""
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)|[^가-힣A-Za-z0-9]", "", job["title"]).lower()
    c = re.sub(r"\(주\)|㈜|주식회사|[^가-힣A-Za-z0-9]", "", job.get("company", "")).lower()
    return f"{c}|{t}"


def main():
    now = datetime.now(KST)
    now_s = now.strftime("%Y-%m-%d %H:%M")
    old = load(DATA_FILE, {"jobs": [], "sources": {}})
    seen = set(load(SEEN_FILE, []))
    first_run = len(seen) == 0
    old_jobs = {j["uid"]: j for j in old.get("jobs", [])}
    old_status = old.get("sources", {})

    # ① 수집
    collected, status = [], {}
    for name, fn in SOURCES:
        t0 = time.time()
        try:
            jobs = fn()
            collected.extend(jobs)
            status[name] = {"ok": True, "count": len(jobs), "fails": 0, "checked": now_s,
                            "last_ok": now_s, "error": ""}
            print(f"✅ {name}: {len(jobs)}건 ({time.time() - t0:.1f}초)")
        except Exception as e:
            prev = old_status.get(name, {})
            status[name] = {"ok": False, "count": 0, "fails": prev.get("fails", 0) + 1, "checked": now_s,
                            "last_ok": prev.get("last_ok", ""), "error": f"{type(e).__name__}: {e}"[:200]}
            print(f"❌ {name}: {e}")
            traceback.print_exc(limit=1)

    # ② 분류 + ③ 새 공고 찾기
    merged = {}
    for j in collected:
        if not j.get("title"):
            continue
        j["categories"] = classify(j)
        j["intern"] = is_intern(j)
        prev = old_jobs.get(j["uid"])
        j["first_seen"] = prev["first_seen"] if prev else now_s
        j["last_seen"] = now_s
        merged[j["uid"]] = j

    # 이번에 실패한 사이트의 기존 공고는 그대로 유지 (실패했다고 지우지 않음)
    failed = {n for n, s in status.items() if not s["ok"]}
    cutoff = (now - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d %H:%M")
    today = now.strftime("%Y-%m-%d")
    valid_sources = {n for n, _ in SOURCES}
    for uid, j in old_jobs.items():
        if uid in merged or j.get("source") not in valid_sources:   # 삭제·이름변경된 사이트 정리
            continue
        deadline_ok = j.get("deadline", "") >= today if re.match(r"\d{4}-", j.get("deadline", "")) else True
        if j["source"] in failed or (j["last_seen"] >= cutoff and deadline_ok):
            merged[uid] = j

    new_jobs = [j for j in merged.values() if j["uid"] not in seen]

    # 다른 사이트에 이미 올라왔던 같은 공고는 알림에서 제외
    seen_keys = {norm_key(j) for j in merged.values() if j["uid"] in seen}
    to_notify, keys_now = [], set()
    for j in new_jobs:
        k = norm_key(j)
        if k in seen_keys or k in keys_now:
            continue
        keys_now.add(k)
        if NOTIFY_INTERN_ONLY and not j["intern"]:
            continue
        if NOTIFY_MODE == "focus" and j["categories"] == ["기타"]:
            continue
        to_notify.append(j)

    # ④ 저장
    jobs_sorted = sorted(merged.values(), key=lambda x: (x["first_seen"], x.get("posted", "")), reverse=True)
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps({"updated": now_s, "sources": status, "jobs": jobs_sorted},
                                    ensure_ascii=False, indent=1), encoding="utf-8")
    seen |= {j["uid"] for j in merged.values()}
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(sorted(seen)[-30000:], ensure_ascii=False), encoding="utf-8")
    print(f"\n총 {len(jobs_sorted)}건 저장 · 새 공고 {len(new_jobs)}건 · 알림 대상 {len(to_notify)}건")

    # ⑤ 텔레그램
    if first_run:
        send(f"✅ <b>인턴 공고 대시보드 연결 완료</b>\n현재 공고 {len(jobs_sorted)}건을 기억했어요. "
             f"이제부터 새로 올라오는 공고만 알려드릴게요." + (f"\n📊 {DASHBOARD_URL}" if DASHBOARD_URL else ""))
    else:
        send_new_jobs(to_notify, DASHBOARD_URL)

    broken = [f"• {n}: {s['error']}" for n, s in status.items()
              if not s["ok"] and s["fails"] == FAIL_ALERT_AFTER]
    if broken:
        send("⚠️ <b>수집이 연속 실패한 사이트</b>\n" + "\n".join(broken))


if __name__ == "__main__":
    main()
