"""
각 공고 사이트에서 공고 목록을 읽어오는 '수집기' 모음입니다.

모든 수집기는 같은 모양의 공고(dict) 리스트를 돌려줍니다:
    {
        "uid":      "사이트코드:공고번호"  (중복 확인용 고유 ID)
        "source":   사이트 이름
        "title":    공고 제목
        "company":  기업명 (모르면 "")
        "url":      공고 바로가기 주소
        "deadline": 마감일 "YYYY-MM-DD" 또는 "상시" 등 문자열 (모르면 "")
        "posted":   게시일 "YYYY-MM-DD" (모르면 "")
        "tags":     사이트가 붙여준 직무/분야 태그 리스트
    }
"""
import json
import re
import time
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

KST = timezone(timedelta(hours=9))
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}
TIMEOUT = 20


# ───────────────────────── 공통 도우미 ─────────────────────────
def get(url, **kw):
    r = requests.get(url, headers={**HEADERS, **kw.pop("headers", {})}, timeout=TIMEOUT, **kw)
    r.raise_for_status()
    return r


def soup_of(url, **kw):
    r = get(url, **kw)
    r.encoding = r.apparent_encoding if r.encoding in (None, "ISO-8859-1") else r.encoding
    return BeautifulSoup(r.text, "html.parser")


def clean(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def ts_to_date(ms):
    """밀리초 타임스탬프 → YYYY-MM-DD"""
    if not ms:
        return ""
    return datetime.fromtimestamp(int(ms) / 1000, KST).strftime("%Y-%m-%d")


def norm_date(text):
    """'26-11-20', '2026.11.22', '~11.25(수)', '2026-11-12 14:00' 같은 걸 YYYY-MM-DD로."""
    if not text:
        return ""
    t = clean(text)
    now = datetime.now(KST)
    m = re.search(r"(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})", t)
    if m:
        return f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}"
    m = re.search(r"\b(\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})\b", t)
    if m:
        return f"20{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}"
    m = re.search(r"(\d{1,2})[./](\d{1,2})", t)
    if m:
        mon, day = int(m[1]), int(m[2])
        if 1 <= mon <= 12 and 1 <= day <= 31:
            year = now.year + (1 if mon < now.month - 6 else 0)  # 연말에 1월 마감 공고 처리
            return f"{year:04d}-{mon:02d}-{day:02d}"
    for word in ("상시", "채용시", "수시"):
        if word in t:
            return "상시"
    return ""


def company_from_title(title):
    """'[교보자산운용] 재무전략본부 채용' → '교보자산운용',  '아우모비오｜인턴십' → '아우모비오'"""
    m = re.match(r"\s*\[([^\]]+)\]", title)
    if m and not re.search(r"intern|full time|신입|경력|인턴", m[1], re.I):
        return clean(m[1])
    if "｜" in title:
        return clean(title.split("｜")[0])
    return ""


# ───────────────────────── 1. 성균관대 인턴채용 ─────────────────────────
def skku():
    base = "https://job.skku.edu"
    soup = soup_of(f"{base}/Recruit/RecruitInternList.aspx")
    out = []
    for tr in soup.select("tr[id^=hcTr]"):
        tds = tr.find_all("td")
        a = tr.find("a", href=re.compile("detailView"))
        if not a or len(tds) < 4:
            continue
        m = re.search(r"detailView\('([^']+)',\s*'(\d+)'\)", a["href"])
        if not m:
            continue
        badges = [clean(s.get_text()) for s in tds[2].find_all("span")]
        out.append({
            "uid": f"skku:{m[2]}",
            "source": "성균관대",
            "title": clean(a.get_text()),
            "company": clean(tds[1].get_text()),
            "url": f"{base}/Recruit/RecruitView.aspx?rcdx={m[1]}&modalChk=Y",
            "deadline": norm_date(tds[3].get_text()),
            "posted": "",
            "tags": badges,
        })
    return out


# ───────────────────────── 2,6,7. 네이버 카페 게시판 ─────────────────────────
NAVER_CAFES = [
    # (화면에 보일 이름, 카페 ID, 게시판 ID)  ← 이름은 자유롭게 바꿔도 됩니다
    ("네카페·공기업/금융공기업", 15279069, 601),
    ("네카페·금융권 인턴", 23690164, 214),
    ("네카페·컨설팅 RA", 18633550, 143),
]
NAVER_MAX_AGE_DAYS = 60   # 올라온 지 이 날짜보다 오래된 글은 제외


def deadline_from_title(title, posted):
    """제목 속 마감일 읽기: '(~11/25)', '(~10월19일)', '(~11.14)', '(11/11~11/25)', '2026.11.18 제출 마감'"""
    if re.search(r"채용\s*시|상시", title):
        return "상시"
    seg = title.rsplit("~", 1)[1] if "~" in title else (
        title if re.search(r"마감|due|까지", title, re.I) else "")
    if not seg:
        return ""
    m = re.search(r"(20\d{2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{1,2})", seg)
    if m:
        return f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}"
    m = (re.search(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", seg)
         or re.search(r"(?<!\d)(\d{1,2})\s*[./]\s*(\d{1,2})(?!\d)", seg))
    if not m:
        return ""
    mon, day = int(m[1]), int(m[2])
    if not (1 <= mon <= 12 and 1 <= day <= 31):
        return ""
    year = int(posted[:4]) if posted else datetime.now(KST).year
    d = f"{year:04d}-{mon:02d}-{day:02d}"
    if posted and d < posted:          # 12월에 올라온 '~1/10' 공고 → 다음 해
        d = f"{year + 1:04d}-{mon:02d}-{day:02d}"
    return d


def naver_cafe(name, club_id, menu_id):
    """네이버 카페 공개 게시판 목록. 회원만 볼 수 있는 게시판이면 에러가 납니다."""
    headers = {"Referer": "https://cafe.naver.com/"}
    items = None
    # 신형 주소 먼저, 실패하면 구형 주소
    try:
        url = (f"https://apis.naver.com/cafe-web/cafe-boardlist-api/v1/cafes/{club_id}"
               f"/menus/{menu_id}/articles?page=1&pageSize=50&sortBy=TIME&viewType=L")
        data = get(url, headers=headers).json()
        items = [x.get("item", x) for x in data["result"]["articleList"]]
    except Exception:
        url = ("https://apis.naver.com/cafe-web/cafe2/ArticleListV2dot1.json"
               f"?search.clubid={club_id}&search.menuid={menu_id}&search.page=1&search.perPage=50")
        data = get(url, headers=headers).json()
        items = data["message"]["result"]["articleList"]
    out = []
    oldest = (datetime.now(KST) - timedelta(days=NAVER_MAX_AGE_DAYS)).strftime("%Y-%m-%d")
    for it in items:
        aid = it.get("articleId")
        title = clean(it.get("subject", ""))
        posted = ts_to_date(it.get("writeDateTimestamp"))
        if not aid or not title or (posted and posted < oldest):
            continue
        out.append({
            "uid": f"naver{club_id}:{aid}",
            "source": name,
            "title": title,
            "company": company_from_title(title),
            "url": f"https://cafe.naver.com/f-e/cafes/{club_id}/articles/{aid}",
            "deadline": deadline_from_title(title, posted),
            "posted": posted,
            "tags": [clean(it.get("headName", ""))] if it.get("headName") else [],
        })
    return out


# ───────────────────────── 3. 금융투자협회 채용안내 ─────────────────────────
KOFIA_PAGES = 3                                        # 몇 페이지까지 읽을지
KOFIA_KEEP = re.compile(r"인턴|intern|단기\s*계약", re.I)  # 제목에 이 단어가 있는 공고만 남김


def kofia():
    base = "https://www.kofia.or.kr/brd/m_96/"
    out, seen = [], set()
    for page in range(1, KOFIA_PAGES + 1):
        soup = soup_of(f"{base}list.do?page={page}")
        out += _kofia_rows(soup, base, seen)
        time.sleep(1)
    return out


def _kofia_rows(soup, base, seen):
    out = []
    # 이 사이트는 HTML의 <a> 태그가 잘못 짜여 있어서(<span><a></span>제목</a>),
    # 링크 안 글자 대신 '제목 칸 전체 글자'와 'view.do?seq=번호'를 따로 읽습니다.
    for tr in soup.find_all("tr"):
        m = re.search(r"view\.do\?seq=(\d+)", str(tr))
        tds = tr.find_all("td", recursive=False)
        if not m or len(tds) < 4:
            continue
        seq = m[1]
        title_td = next((td for td in tds if "view.do?seq=" in str(td)), tds[2])
        title = clean(title_td.get_text())
        if not title or seq in seen or not KOFIA_KEEP.search(title):
            continue
        seen.add(seq)
        out.append({
            "uid": f"kofia:{seq}",
            "source": "금융투자협회",
            "title": title,
            "company": clean(tds[1].get_text()),
            "url": f"{base}view.do?seq={seq}",
            "deadline": norm_date(re.search(r"~\s*[\d/.]+", title)[0]) if re.search(r"~\s*[\d/.]+", title) else "",
            "posted": norm_date(tds[-1].get_text()),
            "tags": ["금융투자"],
        })
    return out


# ───────────────────────── 4. 자소설닷컴 (인턴) ─────────────────────────
def jasoseol():
    soup = soup_of("https://jasoseol.com/search?division=3")
    nd = json.loads(soup.find("script", id="__NEXT_DATA__").string)
    pp = nd["props"]["pageProps"]
    duty_names = {}

    def walk(x):  # 직무 id → 이름 표 만들기
        if isinstance(x, dict):
            if "id" in x and "name" in x:
                duty_names[x["id"]] = x["name"]
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(pp.get("duties", []))

    rows = []
    for q in pp["dehydratedState"]["queries"]:
        d = (q.get("state") or {}).get("data") or {}
        if isinstance(d.get("data"), list):
            rows.extend(d["data"])
    out = []
    for r in rows:
        tags, fields = [], []
        for e in r.get("employments") or []:
            if e.get("field"):
                fields.append(e["field"])
            for gid in e.get("duty_group_ids") or []:
                if gid in duty_names:
                    tags.append(duty_names[gid])
        out.append({
            "uid": f"jasoseol:{r['id']}",
            "source": "자소설닷컴",
            "title": clean(r.get("title")),
            "company": clean(r.get("name")),
            "url": f"https://jasoseol.com/recruit/{r['id']}",
            "deadline": norm_date(r.get("end_time")) if r.get("end_time") else "상시",
            "posted": norm_date(r.get("created_at")),
            "tags": sorted(set(tags + fields)),
        })
    return out


# ───────────────────────── 5. 링커리어 (인턴) ─────────────────────────
def linkareer(pages=2):
    out = []
    for page in range(1, pages + 1):
        url = ("https://linkareer.com/list/intern?filterBy_activityTypeID=5&filterBy_jobTypes=INTERN"
               f"&filterBy_status=OPEN&orderBy_direction=DESC&orderBy_field=RECENT&page={page}")
        soup = soup_of(url)
        st = json.loads(soup.find("script", id="__NEXT_DATA__").string)["props"]["pageProps"]["__APOLLO_STATE__"]
        for key, v in st.items():
            if not key.startswith("Activity:") or v.get("__typename") != "Activity":
                continue
            cats = []
            for c in v.get("categories") or []:
                ref = st.get(c.get("__ref", ""), {})
                if ref.get("name") and ref["name"] != "전체":
                    cats.append(ref["name"])
            out.append({
                "uid": f"linkareer:{v['id']}",
                "source": "링커리어",
                "title": clean(v.get("title")),
                "company": clean(v.get("organizationName")),
                "url": f"https://linkareer.com/activity/{v['id']}",
                "deadline": ts_to_date(v.get("recruitCloseAt")),
                "posted": "",
                "tags": cats,
            })
        time.sleep(1)
    return out


# ───────────────────────── 8. 연세대 MBA 채용정보 ─────────────────────────
def yonsei_mba():
    base = "https://mba.yonsei.ac.kr/mba/career/recruitment.do"
    soup = soup_of(base + "?article.offset=0&articleLimit=30")
    out = []
    for tr in soup.select("table tbody tr"):
        a = tr.find("a", attrs={"data-article-no": True})
        tds = tr.find_all("td")
        if not a or len(tds) < 5:
            continue
        no = a["data-article-no"]
        title = clean(a.get("title", a.get_text())).replace(" 자세히 보기", "")
        out.append({
            "uid": f"yonsei:{no}",
            "source": "연세대 MBA",
            "title": title,
            "company": company_from_title(title),
            "url": f"{base}?mode=view&articleNo={no}",
            "deadline": norm_date(tds[4].get_text()),
            "posted": "",
            "tags": [clean(tds[3].get_text()).replace(" 전체", "")],
        })
    return out


# ───────────────────────── 9. 커리어점프 취업공고 ─────────────────────────
def careerjump():
    soup = soup_of("https://careerjump.co.kr/board/%EC%B7%A8%EC%97%85%EA%B3%B5%EA%B3%A0/articles")
    out, seen = [], set()
    for tr in soup.select("tr"):
        a = tr.select_one("a.board-list")
        if not a:
            continue
        aid = re.search(r"/articles/(\d+)", a["href"])[1]
        if aid in seen:
            continue
        seen.add(aid)
        title = clean(a.get_text())
        cat = re.match(r"\[([^\]]+)\]", title)
        date = tr.select_one("td.list-date")
        out.append({
            "uid": f"careerjump:{aid}",
            "source": "커리어점프",
            "title": title,
            "company": "",
            "url": a["href"].split("?")[0],
            "deadline": "",
            "posted": norm_date(date.get_text()) if date else "",
            "tags": [cat[1]] if cat else [],
        })
    return out


# ───────────────────────── 10. 인디스워크 신입/인턴 ─────────────────────────
def inthiswork():
    api = "https://inthiswork.com/wp-json/wp/v2"
    posts = get(f"{api}/posts?categories=191700167&per_page=50&_fields=id,date,link,title,tags").json()
    tag_ids = sorted({t for p in posts for t in p.get("tags", [])})
    names = {}
    for i in range(0, len(tag_ids), 90):
        chunk = ",".join(map(str, tag_ids[i:i + 90]))
        for t in get(f"{api}/tags?include={chunk}&per_page=100&_fields=id,name").json():
            names[t["id"]] = t["name"]
    out = []
    for p in posts:
        title = BeautifulSoup(p["title"]["rendered"], "html.parser").get_text()
        tags = [names[t] for t in p.get("tags", []) if t in names and names[t] not in ("기한있음", "상시채용")]
        out.append({
            "uid": f"inthiswork:{p['id']}",
            "source": "인디스워크",
            "title": clean(title),
            "company": company_from_title(title),
            "url": p["link"],
            "deadline": "",
            "posted": p["date"][:10],
            "tags": tags,
        })
    return out


# ───────────────────────── 11. 잡코리아 신입·인턴 채용관 ─────────────────────────
def jobkorea():
    base = "https://www.jobkorea.co.kr"
    q = ("rlistTab=0&rOrderTab=1&bpart_no=0&jobFilter=1&listDisplayCode=2&MainPageNo=1&FreePageNo=1"
         "&psTab=40&themeNo=169&tabNo=0&giDisplayCntLimitStat=0&GIOpenTypeCode=0&IsPartCodeSearch=false")
    out, seen = [], set()
    for kind in ("TemplateMainGnoList", "TemplateFreeGnoList"):
        soup = soup_of(f"{base}/Theme/{kind}/entry-level-internship?{q}")
        for tr in soup.select("tr.devloopArea"):
            a = tr.select_one("a.dev-recruit-link")
            if not a:
                continue
            gno = re.search(r"GI_Read/(\d+)", a["href"])[1]
            if gno in seen:
                continue
            seen.add(gno)
            co = tr.select_one("td.tplCo a")
            cells = [clean(s.get_text()) for s in tr.select("p.etc .cell")]
            dsc = tr.select_one("p.dsc")
            dl = re.search(r"~\s?\d{1,2}/\d{1,2}|상시채용|채용시", tr.get_text())
            out.append({
                "uid": f"jobkorea:{gno}",
                "source": "잡코리아",
                "title": clean(a.get("title") or a.get_text()),
                "company": clean(co.get_text()) if co else "",
                "url": f"{base}/Recruit/GI_Read/{gno}",
                "deadline": norm_date(dl[0]) if dl else "",
                "posted": "",
                "tags": cells[-2:-1] + ([clean(dsc.get_text())[:80]] if dsc else []),
            })
        time.sleep(1)
    return out


# ───────────────────────── 12. 사람인 인턴 ─────────────────────────
def saramin():
    base = "https://www.saramin.co.kr"
    soup = soup_of(f"{base}/zf_user/jobs/public/list?page=1&type=intern")
    out = []
    for div in soup.select("div.list_item[id^=rec-]"):
        rid = div["id"].split("-")[1]
        a = div.select_one(".job_tit a")
        co = div.select_one(".company_nm .str_tit")
        if not a:
            continue
        sectors = [clean(s.get_text()) for s in div.select(".job_sector span")]
        date = div.select_one(".support_detail .date")
        out.append({
            "uid": f"saramin:{rid}",
            "source": "사람인",
            "title": clean(a.get("title") or a.get_text()),
            "company": clean(co.get_text()) if co else "",
            "url": f"{base}/zf_user/jobs/relay/view?view_type=public-recruit&rec_idx={rid}",
            "deadline": norm_date(date.get_text()) if date else "",
            "posted": "",
            "tags": sectors[:6],
        })
    return out


# ───────────────────────── 13. 직행 (체험형·전환형 인턴) ─────────────────────────
def zighang(size=100):
    api = ("https://api.zighang.com/api/recruitments/v4?page=0&size={size}&includeCareerOpen=true"
           "&sortCondition=LATEST&orderCondition=DESC&employeeTypes=%EC%B2%B4%ED%97%98%ED%98%95%EC%9D%B8%ED%84%B4"
           "%2C%EC%A0%84%ED%99%98%ED%98%95%EC%9D%B8%ED%84%B4")  # employeeTypes=체험형인턴,전환형인턴
    data = get(api.format(size=size), headers={"Origin": "https://zighang.com",
                                               "Referer": "https://zighang.com/"}).json()
    if not data.get("success"):
        raise RuntimeError(data.get("message", "직행 API 응답 오류")[:150])
    out = []
    for r in data["data"]["content"]:
        fields = [x.replace("_", "·") for x in (r.get("depthOnes") or []) + (r.get("depthTwos") or [])]
        if r.get("endDate"):
            deadline = norm_date(r["endDate"])
        elif r.get("deadlineType") in ("상시채용", "채용시마감"):
            deadline = "상시"
        else:
            deadline = ""
        out.append({
            "uid": f"zighang:{r['id']}",
            "source": "직행",
            "title": clean(r.get("title")),
            "company": clean((r.get("company") or {}).get("name")),
            "url": f"https://zighang.com/recruitment/{r['id']}",
            "deadline": deadline,
            "posted": norm_date(r.get("createdAt")),
            "tags": (r.get("employeeTypes") or []) + fields + (r.get("keywords") or [])[:3],
        })
    return out


# 실행할 수집기 목록: (이름, 함수)
SOURCES = [
    ("성균관대", skku),
    *[(n, (lambda n=n, c=c, m=m: naver_cafe(n, c, m))) for n, c, m in NAVER_CAFES],
    ("금융투자협회", kofia),
    ("자소설닷컴", jasoseol),
    ("링커리어", linkareer),
    ("연세대 MBA", yonsei_mba),
    ("커리어점프", careerjump),
    ("인디스워크", inthiswork),
    ("잡코리아", jobkorea),
    ("사람인", saramin),
    ("직행", zighang),
]
