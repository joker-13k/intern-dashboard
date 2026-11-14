# 인턴 공고 대시보드 + 텔레그램 알림 · 설치 가이드

12개 사이트의 인턴 공고를 **2시간마다 자동으로** 모아서
① 웹 대시보드(금융권 / 전략기획 / 기타)에 보여주고
② 새 공고가 올라오면 **텔레그램으로 알려주는** 프로그램입니다.

모든 작업은 GitHub의 무료 서버에서 돌아가기 때문에 **내 컴퓨터를 꺼도 작동**합니다.

---

## 폴더 구조: 각 파일이 하는 일

```
intern-dashboard/
├─ scraper/                 ← 파이썬 프로그램 (실제 일하는 곳)
│   ├─ sources.py           각 사이트에서 공고를 읽어오는 수집기 12개
│   ├─ classify.py          금융권 / 전략기획 분류 기준 단어  ← 자유롭게 수정 가능
│   ├─ notify.py            텔레그램 메시지 보내기
│   └─ main.py              전체 순서 실행 (수집 → 분류 → 새 공고 찾기 → 저장 → 알림)
├─ docs/
│   ├─ index.html           대시보드 화면
│   └─ data.json            수집된 공고 데이터 (자동으로 갱신됨)
├─ data/seen.json           이미 알림 보낸 공고 목록 (자동 생성)
├─ .github/workflows/update.yml   ← "2시간마다 실행해라"라는 예약 설정
└─ requirements.txt         필요한 파이썬 라이브러리 목록
```

---

## 1단계 · 텔레그램 봇 만들기 (5분)

1. 텔레그램에서 **@BotFather**를 검색해서 대화를 시작합니다.
2. `/newbot`을 보냅니다.
3. 봇 이름을 입력합니다. (예: `민준 인턴알리미`)
4. 봇 아이디를 입력합니다. 반드시 `bot`으로 끝나야 해요. (예: `minjun_intern_bot`)
5. BotFather가 `123456789:ABCdef...` 같은 **토큰**을 줍니다. 메모해 두세요.
   이 토큰은 비밀번호와 같아서 다른 사람에게 보여주면 안 됩니다.
6. 방금 만든 봇을 검색해서 들어가 **아무 메시지나 하나** 보냅니다. (예: `안녕`)
7. 인터넷 브라우저 주소창에 아래 주소를 입력합니다. `<토큰>` 자리에 5번에서 받은 토큰을 넣으세요.
   ```
   https://api.telegram.org/bot<토큰>/getUpdates
   ```
8. 화면에 나온 글에서 `"chat":{"id":123456789` 부분의 **숫자**를 찾아 메모합니다.
   이것이 **채팅 ID**입니다.

---

## 2단계 · VS Code로 폴더 열기

1. 받은 `intern-dashboard.zip`의 압축을 풉니다. (예: 바탕화면이나 문서 폴더)
2. VS Code를 켜고 상단 메뉴에서 **File → Open Folder…**를 누른 뒤 `intern-dashboard` 폴더를 선택합니다.
3. "Do you trust the authors?" 창이 뜨면 **Yes, I trust**를 누릅니다.
4. 왼쪽 탐색기에 위 폴더 구조가 보이면 성공입니다.

---

## 3단계 · (선택이지만 추천) 내 컴퓨터에서 먼저 시험 실행

이 단계는 사이트에서 공고를 잘 가져오는지 미리 확인하는 용도예요.

1. VS Code 상단 메뉴에서 **Terminal → New Terminal**을 엽니다. 화면 아래에 검은 창이 생겨요.
2. 파이썬이 설치되어 있는지 확인합니다.
   ```
   python --version
   ```
   - `Python 3.x.x`가 나오면 OK입니다.
   - 에러가 나면 https://www.python.org/downloads/ 에서 설치하세요.
     Windows는 설치 첫 화면에서 **"Add python.exe to PATH"를 꼭 체크**해야 합니다. 설치 후 VS Code를 껐다 켜세요.
   - Mac에서는 `python` 대신 `python3`, `pip` 대신 `pip3`를 입력하세요.
3. 필요한 라이브러리를 설치합니다.
   ```
   pip install -r requirements.txt
   ```
4. 실행합니다.
   ```
   python scraper/main.py
   ```
5. 아래처럼 사이트별 결과가 찍히면 성공입니다.
   ```
   ✅ 성균관대: 20건
   ✅ 링커리어: 40건
   ❌ 네이버카페 A (15279069): ...
   ```
   ❌가 뜬 사이트가 있으면 그 줄을 그대로 복사해서 Claude에게 보여주세요.
6. 시험이 끝났으면 `data/seen.json` 파일을 삭제해 주세요.
   그래야 GitHub에서 처음 실행될 때 텔레그램 "연결 완료" 메시지를 받을 수 있어요.

---

## 4단계 · GitHub에 올리기

1. VS Code 왼쪽 세로 아이콘 중 **소스 제어**(갈래길 모양 아이콘, 단축키 `Ctrl+Shift+G`)를 누릅니다.
2. **Publish to GitHub** 버튼을 누릅니다.
   - 처음이면 GitHub 로그인 창이 뜹니다. 로그인하고 허용해 주세요.
3. 저장소 이름은 `intern-dashboard`로 두고 **Publish to GitHub public repository**를 선택합니다.
   - 무료 계정에서 대시보드 웹페이지(GitHub Pages)를 쓰려면 public(공개)이어야 해요.
   - 공개되는 것은 공고 목록과 코드뿐이고, 텔레그램 토큰은 5단계에서 비밀 금고(Secrets)에 넣기 때문에 공개되지 않습니다.
4. 업로드할 파일을 고르라는 창이 나오면 **전부 선택**한 상태로 OK를 누릅니다.
5. 끝나면 오른쪽 아래에 **Open on GitHub** 버튼이 뜹니다. 눌러서 GitHub 페이지를 엽니다.

---

## 5단계 · 텔레그램 정보를 GitHub 비밀 금고에 넣기

GitHub의 내 저장소 페이지에서 진행합니다.

1. 위쪽 탭 중 **Settings**를 누릅니다.
2. 왼쪽 메뉴에서 **Secrets and variables → Actions**를 누릅니다.
3. **Secrets** 탭에서 **New repository secret**을 눌러 아래 두 개를 만듭니다.

   | Name (정확히 이대로) | Secret (값) |
   |---|---|
   | `TELEGRAM_BOT_TOKEN` | 1단계 5번의 토큰 |
   | `TELEGRAM_CHAT_ID` | 1단계 8번의 숫자 |

4. 옆의 **Variables** 탭으로 가서 **New repository variable**을 누릅니다.
   - Name: `DASHBOARD_URL`
   - Value: `https://내GitHub아이디.github.io/intern-dashboard/`
   - 이 주소를 넣어 두면 텔레그램 메시지에 대시보드 링크가 붙어요.

---

## 6단계 · 자동 실행 권한과 대시보드 웹페이지 켜기

1. **Settings → Actions → General**로 갑니다.
   맨 아래 **Workflow permissions**에서 **Read and write permissions**를 선택하고 **Save**를 누릅니다.
2. **Settings → Pages**로 갑니다.
   - Source: **Deploy from a branch**
   - Branch: **main**, 폴더: **/docs**
   - **Save**를 누릅니다.
   - 1~2분 뒤 위쪽에 대시보드 주소가 표시됩니다.

---

## 7단계 · 첫 실행

1. 저장소 위쪽 탭에서 **Actions**를 누릅니다.
2. 왼쪽 목록에서 **인턴 공고 업데이트**를 누릅니다.
3. 오른쪽의 **Run workflow → Run workflow** 버튼을 누릅니다.
4. 1~2분 기다리면 초록색 ✅이 뜹니다.
   - 텔레그램으로 **"✅ 인턴 공고 대시보드 연결 완료"** 메시지가 와요.
   - 대시보드 주소에 들어가면 공고 목록이 보입니다.
5. 이후로는 **2시간마다 자동으로 실행**되고, 새 공고가 있을 때만 텔레그램이 옵니다.

빨간 ❌이 뜨면 해당 실행을 클릭하고 **update** 안의 빨간 줄을 캡처해서 Claude에게 보여주세요.

---

## 원하는 대로 바꾸기

| 바꾸고 싶은 것 | 방법 |
|---|---|
| 분류 기준 단어 | `scraper/classify.py`의 `FINANCE`, `STRATEGY` 목록에 단어를 추가하거나 삭제 |
| 모든 새 공고 알림 받기 | GitHub Variables에 `NOTIFY_MODE` = `all` 추가 (기본값은 금융권·전략기획만 알림) |
| 실행 주기 | `.github/workflows/update.yml`의 `cron: "0 */2 * * *"`에서 `2`를 원하는 시간 간격으로 변경 |
| 사이트 추가/삭제 | `scraper/sources.py` 맨 아래 `SOURCES` 목록에서 해당 줄을 추가하거나 삭제 |

코드를 고친 뒤에는 VS Code 소스 제어 탭에서 다음 순서로 GitHub에 반영합니다.
1. 메시지 칸에 변경 내용을 적습니다. (예: `키워드 수정`)
2. **Commit**을 누릅니다.
3. **Sync Changes**를 누릅니다.

---

## 알아둘 점

- **수집이 막힌 사이트는 대시보드 맨 아래 "사이트별 수집 상태"에서 확인할 수 있어요.**
  같은 사이트가 3번 연속 실패하면 텔레그램으로도 경고가 옵니다.
- **네이버 카페 3곳은 회원만 볼 수 있는 게시판이면 수집이 안 됩니다.**
  GitHub 서버는 해외(미국)에 있어서 일부 국내 사이트가 접속을 막을 수도 있어요.
  이런 경우 대안으로 ① 그 사이트만 내 컴퓨터에서 실행하는 방식, ② 해당 사이트 제외를 함께 검토하면 됩니다.
- 사이트 디자인이 바뀌면 그 사이트 수집기만 고치면 됩니다. 다른 사이트는 계속 정상 작동해요.
- 사람인·잡코리아 등은 이용약관에 자동 수집 제한 조항이 있어요. 2시간에 한 번 첫 페이지만 읽는 개인용 수준으로 설정해 두었습니다.
- GitHub의 예약 실행은 서버 사정에 따라 수 분~수십 분 늦게 시작될 수 있어요.
