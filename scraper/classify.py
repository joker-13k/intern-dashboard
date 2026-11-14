"""
공고를 '금융권' / '전략기획' / '기타'로 분류합니다.
분류 기준 단어는 아래 리스트를 고치면 바로 바뀝니다. (단어 추가·삭제 자유)
한 공고가 금융권이면서 전략기획일 수도 있습니다. (예: 증권사 경영기획 인턴)
"""
import re

# 기업명/제목/태그에 이 단어가 들어가면 → 금융권
FINANCE = [
    "금융", "은행", "증권", "자산운용", "운용사", "투자", "보험", "생명", "손해보험", "화재", "캐피탈",
    "카드사", "뱅크", "핀테크", "파이낸셜", "카카오페이", "토스", "현대카드", "삼성카드", "신한카드", "저축은행", "신용평가", "평가정보", "신용정보", "펀드", "애널리스트", "트레이딩", "채권",
    "대체투자", "사모", "벤처캐피탈", "파생", "리스크관리", "자산관리", "WM", "IB", "PE", "VC",
    "S&T", "M&A", "ECM", "DCM", "PF", "Investment", "Capital", "Securities", "Asset", "Bank",
    "Fund", "Equity", "Credit", "Advisory",
    # 주요 금융기관 이름
    "KB", "신한", "하나은행", "하나증권", "하나금융", "우리금융", "우리은행", "NH", "농협", "IBK", "기업은행", "미래에셋", "한국투자",
    "삼성증권", "삼성자산", "키움", "교보", "메리츠", "대신", "유안타", "한화투자", "한화자산", "DB금융",
    "다이와", "노무라", "골드만", "모건", "JP Morgan", "맥쿼리", "Macquarie", "PIMCO", "블랙록",
    "BlackRock", "UBS", "씨티", "HSBC", "한국은행", "산업은행", "수출입은행", "금융감독원", "금감원",
    "한국거래소", "예탁결제원", "예금보험공사", "신용보증", "기술보증", "주택금융공사", "한국투자공사",
    "국민연금", "NICE", "한국기업평가", "한국신용평가", "회계법인",
]

# 전략기획 / 컨설팅 계열
STRATEGY = [
    "전략", "경영기획", "사업기획", "기획조정", "경영관리", "사업개발", "신사업", "사업전략",
    "컨설팅", "컨설턴트", "Consulting", "Strategy", "Strategic", "Corporate Development",
    "BD", "Business Development", "PMO", "MBB", "맥킨지", "McKinsey", "BCG", "Boston Consulting",
    "베인", "Bain", "Kearney", "커니", "롤랜드버거", "Roland Berger", "올리버와이먼", "Oliver Wyman",
    "L.E.K", "Strategy&", "Monitor Deloitte", "사업기획/신규사업", "M&A",
]

# '생명'이 들어가도 금융이 아닌 표현들
FINANCE_EXCLUDE = ["생명과학", "생명공학", "생명연구", "투자유치"]

# '전략'이 들어가도 전략기획이 아닌 표현들 (먼저 지운 뒤 판단)
STRATEGY_EXCLUDE = [
    "마케팅기획/전략", "마케팅 전략", "마케팅전략", "브랜드 전략", "브랜드전략", "콘텐츠 전략",
    "콘텐츠전략", "영업전략", "광고전략", "SNS 전략",
]

INTERN_WORDS = ["인턴", "단기계약", "단기 계약", "intern", "Intern", "INTERN", "RA", "체험형", "채용연계", "채용전환", "인턴십", "Internship"]


def _has(words, text):
    for w in words:
        if re.fullmatch(r"[A-Za-z&.]{1,4}", w):          # IB, PE, KB 같은 짧은 영어는 단어 단위로만
            if re.search(rf"(?<![A-Za-z]){re.escape(w)}(?![A-Za-z])", text):
                return True
        elif w.lower() in text.lower():
            return True
    return False


def classify(job):
    text = " ".join([job.get("company", ""), job.get("title", ""), " ".join(job.get("tags", []))])
    cats = []
    ftext = text
    for ex in FINANCE_EXCLUDE:
        ftext = ftext.replace(ex, " ")
    if _has(FINANCE, ftext):
        cats.append("금융권")
    stext = text
    for ex in STRATEGY_EXCLUDE:
        stext = stext.replace(ex, " ")
    if _has(STRATEGY, stext):
        cats.append("전략기획")
    return cats or ["기타"]


def is_intern(job):
    text = " ".join([job.get("title", ""), " ".join(job.get("tags", []))])
    return _has(INTERN_WORDS, text) or job.get("source") in ("링커리어", "자소설닷컴", "성균관대", "사람인", "직행")
