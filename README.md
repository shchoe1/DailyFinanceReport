# 한국증시 수급 브리핑 봇

매 평일 아침 **06:00**, 외국인·기관·개인의 당일 수급 방향/규모를 휴리스틱으로 예측하고,
전일 나스닥 시황의 한국 섹터 영향을 분석해 **카카오톡 '나에게 보내기'** 로 발송합니다.
상세 리포트는 `reports/report_YYYY-MM-DD.html` 로도 저장됩니다.

> ⚠️ **면책**: 본 봇의 모든 '예측'은 KRX 대체(네이버 금융)·yfinance **공개 데이터 기반의 확률적 휴리스틱**입니다.
> 외국인/기관/개인의 실제 당일 매매를 보장하지 않으며, **투자 권유가 아닙니다.** 투자 판단·책임은 이용자 본인에게 있습니다.

**실행 방식은 2가지** — ⓐ 로컬 PC(윈도우 작업 스케줄러) 또는 ⓑ **GitHub Actions(클라우드, PC 불필요)**.
클라우드로 돌리려면 아래 [클라우드 실행(GitHub Actions)](#클라우드-실행-github-actions) 참고.

---

## 클라우드 실행 (GitHub Actions)
PC를 켜둘 필요 없이 매 평일 06:00(KST)에 GitHub 서버가 실행 → 리포트 생성 → GitHub Pages 게시 → 카톡 발송.

1. 이 폴더를 **공개(public) GitHub 저장소**로 업로드 (아래 '업로드' 참고)
2. 저장소 **Settings → Secrets and variables → Actions → New repository secret** 로 아래 추가:
   - `KAKAO_REST_API_KEY` — REST API 키
   - `KAKAO_CLIENT_SECRET` — 클라이언트 시크릿(사용 시)
   - `KAKAO_REFRESH_TOKEN` — 로컬 `kakao_token.json` 의 `refresh_token` 값
   - `GH_PAT` *(선택)* — refresh token 자동 회전용 PAT (Secrets: write 권한). 미설정이면 ~2개월마다 위 값을 수동 갱신
3. 저장소 **Settings → Pages → Source: GitHub Actions** 로 설정
4. 카카오 개발자 **앱 > 플랫폼(Web)** 에 `https://<사용자명>.github.io` 등록
5. 저장소 **Actions 탭 → daily-market-briefing → Run workflow** 로 즉시 테스트

> 스케줄은 `.github/workflows/daily.yml` 의 cron `0 21 * * 0-4`(=06:00 KST 월~금). 시간 변경은 UTC 기준으로 수정.
> 클라우드에서는 로컬 작업 스케줄러(`register_task.ps1`)가 필요 없습니다.

### 업로드 (로컬 → GitHub)
```powershell
cd C:\Fin
git remote add origin https://github.com/<사용자명>/<저장소>.git
git branch -M main
git push -u origin main      # 브라우저로 GitHub 로그인 창이 뜨면 인증
```
> `.env`·`kakao_token.json` 등 비밀 파일은 `.gitignore` 로 **업로드에서 자동 제외**됩니다.

---

## 무엇을 분석하나

| 항목 | 방법 | 데이터 출처 |
|---|---|---|
| **직전일 실제 수급** | 외국인/기관/개인 전일 순매수 실측치를 예측과 나란히 표기 | 네이버 금융 투자자별 매매동향 |
| 외국인 당일 방향·규모 | 미국 위험선호(나스닥·필반) + 원/달러 + 최근 수급 추세 | 네이버 금융 + yfinance |
| 기관 당일 방향·규모 | 외국인 역상관 + 자체 포지션 추세 | 네이버 금융 |
| 개인 당일 방향·규모 | 외국인·기관 반대편 + **고객예탁금(매수여력)** 반영 | 네이버 금융 |
| 연기금·기관 리밸런싱 압력 | 20일 누적 순매수 과열도(목표비중 회귀 가정) | 네이버 금융 |
| **원/달러 환율(직전일)** | 레벨·전일대비·5일 추이 (원화 강세=외국인 우호) | yfinance |
| **고객예탁금(직전일)** | 매수 대기자금 레벨·전일/5일 증감 (T+2 공표) | 네이버 증시자금동향 |
| **미국 전일 주요 지수** | 나스닥·S&P500·다우·필라델피아반도체·VIX·10년물·달러인덱스·원달러 등락 | yfinance |
| **KOSPI 개별 종목 + 2일 추이** | 시총 상위 100 유니버스 등락률순 → 상승 상위 10 / 중위 10, **전전날→직전일 화살표**(삼성전자·SK하이닉스 항상 포함) | 네이버 시총 + pykrx OHLCV |
| **주요 뉴스(전일)** | 미국·한국 증시 관련 헤드라인 각 3건 | Google News RSS |
| **주요 이벤트(오늘·내일)** | 미국·한국 경제 일정 각 3건 (옵션 만기일 자동 계산 포함) | ForexFactory 캘린더 + 만기일 계산 |
| 나스닥 → 한국 섹터 영향 | 미국 섹터 ETF 등락 × 전이계수(반도체 최고) | yfinance |

> 각 투자자 통계는 **직전일 실측치**와 **5일/20일 누적**을 함께 제공합니다. 매일 실행할수록 `data/*.csv` 에 이력이 쌓여 누적 통계가 정교해집니다.

> KRX 공식 사이트(`data.krx.co.kr`)는 현재 Akamai 봇 차단으로 프로그램 접근이 막혀 있어, 투자자 수급은 **네이버 금융**에서 수집합니다.

---

## 설치 (최초 1회)

### 1. 파이썬 패키지 (이미 설치됨)
가상환경 `.venv` 와 의존성은 구성 완료 상태입니다. 재설치가 필요하면:
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. 카카오 개발자 앱 만들기  ← **사용자 작업 필요**
1. https://developers.kakao.com → 로그인 → **내 애플리케이션 > 애플리케이션 추가하기**
2. 만든 앱 클릭 → **앱 키 > REST API 키** 복사 (뒤에서 사용)
3. 좌측 **카카오 로그인** → **활성화 설정 ON**
4. **카카오 로그인 > Redirect URI** 에 다음을 정확히 등록:
   ```
   https://localhost:8080
   ```
5. **카카오 로그인 > 동의항목** → **"카카오톡 메시지 전송"(talk_message)** 을 **사용 설정**
   (선택 동의 또는 필수 동의로 켜면 됨)

### 3. `.env` 작성
```powershell
copy .env.example .env
```
`.env` 를 열어 값을 채웁니다:
```
KAKAO_REST_API_KEY=아까_복사한_REST_API_키
KAKAO_REDIRECT_URI=https://localhost:8080
SEND_KAKAO=1
```

### 4. 카카오 최초 인증 (토큰 발급)  ← **사용자 작업 필요**
```powershell
.\.venv\Scripts\python.exe kakao_auth.py
```
- 브라우저가 열리면 카카오 로그인 → **동의**
- 이동한 주소 `https://localhost:8080/?code=XXXX` (페이지가 안 열려도 정상) 의
  **주소창 전체 또는 code 값**을 터미널에 붙여넣기
- 성공하면 `kakao_token.json` 이 생기고, 카카오톡으로 **테스트 메시지**가 옵니다.

### 5. 동작 확인
```powershell
# 발송 없이 리포트만 생성 (reports\ 폴더에 HTML)
.\.venv\Scripts\python.exe main.py --dry-run

# 실제 카카오 발송까지
.\.venv\Scripts\python.exe main.py
```

### 6. 매일 06:00 자동 실행 등록  ← **사용자 작업 필요**
```powershell
.\register_task.ps1
```
- 평일(월~금) 오전 6시에 `run_daily.bat` 이 자동 실행됩니다.
- 즉시 테스트: `Start-ScheduledTask -TaskName KRMarketBriefing` → `reports\run.log` 확인
- 해제: `Unregister-ScheduledTask -TaskName KRMarketBriefing -Confirm:$false`

> **PC가 06:00에 켜져 있어야** 실행됩니다. 꺼져 있었다면 다음 부팅 시 `-StartWhenAvailable` 로 한 번 실행됩니다.

### 7. (선택) 리포트를 폰에서 보기 — GitHub Pages 웹 게시
카톡 '자세히 보기'를 누르면 폰에서 **상세 HTML 리포트 전문**이 열리도록 GitHub Pages에 게시합니다.
1. GitHub에 **공개(public) 저장소** 생성 (예: `market-report`)
2. **PAT 발급**: GitHub → Settings → Developer settings → Personal access tokens →
   Fine-grained token → 그 저장소에 **Contents: Read and write** 권한 → 토큰 복사
3. `.env` 에 추가:
   ```
   GITHUB_USER=깃허브사용자명
   GITHUB_REPO=market-report
   GITHUB_TOKEN=ghp_복사한토큰
   GITHUB_BRANCH=main
   ```
4. `python main.py` 를 한 번 실행 → `site/` 가 저장소에 푸시됨
5. GitHub 저장소 → **Settings → Pages → Source: Deploy from a branch → `main` / `(root)`** 저장
6. 카카오 개발자 **앱 > 플랫폼(Web) 사이트 도메인**에 `https://<사용자명>.github.io` 등록

공개 URL: `https://<사용자명>.github.io/<저장소>/report_YYYY-MM-DD.html`
> 미설정 시에도 리포트는 로컬(`reports/*.html`)에 저장되고 카톡 발송은 정상 진행됩니다.
> 첫 게시 후 Pages 빌드에 1~2분 걸릴 수 있습니다(이후엔 수초).

---

## 파일 구조
```
market-report/
├─ main.py               # 오케스트레이터 (수집→분석→저장→발송)
├─ analyze.py            # 수급 신호·예측·리밸런싱·섹터영향 휴리스틱
├─ report.py            # HTML 리포트 + 카카오 200자 메시지 생성
├─ kakao.py              # 토큰 갱신 + 나에게 보내기
├─ kakao_auth.py         # 최초 1회 OAuth 인증
├─ publish.py            # 리포트를 surge.sh 에 게시(카톡 '자세히 보기' 링크)
├─ config.py             # 경로·상수·섹터 매핑
├─ sources/
│  ├─ investors.py       # 네이버 투자자별 순매수(개인/외국인/기관/연기금)
│  ├─ nasdaq.py          # yfinance 나스닥·섹터ETF·금리 + 원/달러 직전일 상세
│  ├─ sectors_kr.py      # 네이버 업종별 등락
│  ├─ liquidity.py       # 네이버 증시자금동향(고객예탁금·신용잔고)
│  ├─ stocks_kr.py       # KOSPI 개별종목 등락 + 전전날/직전일 2일 추이
│  └─ news.py            # Google News 헤드라인 + ForexFactory 경제 이벤트
├─ data/                 # 수급 이력 누적 CSV (자동 생성)
├─ reports/              # 일별 HTML 리포트 + run.log
├─ run_daily.bat         # 스케줄러가 호출하는 배치
├─ register_task.ps1     # 작업 스케줄러 등록
├─ .env                  # 카카오 키 (직접 작성, git 제외 권장)
└─ requirements.txt
```

---

## 유지보수 메모
- **리프레시 토큰 만료(~2개월)**: 봇이 매일 돌면 자동으로 갱신되어 사실상 만료되지 않습니다.
  2개월 이상 미실행 시에는 `kakao_auth.py` 를 다시 한 번 실행하세요.
- **수급 이력 누적**: 처음엔 최근 ~10일치만 있지만, 매일 실행할수록 `data/*.csv` 에
  쌓여 5일/20일 추세·리밸런싱 계산이 점점 정확해집니다.
- **네이버/야후 구조 변경**: 무료 스크래핑 특성상 사이트 개편 시 파싱이 깨질 수 있습니다.
  그때는 `sources/` 의 해당 파서만 수정하면 됩니다. 한 소스가 실패해도 나머지로 리포트는 계속 생성됩니다.
- **경제 이벤트(ForexFactory)**: 짧은 시간 반복 호출 시 429(호출제한)가 날 수 있어, 성공분을
  `data/ff_calendar.json` 에 캐시해 실패 시 재사용합니다. 하루 1회 운영에선 문제없습니다.
  한국 이벤트는 FF의 한국 커버리지가 얕아 **옵션 만기일 자동계산 + 증시일정 뉴스**로 보완하는 best-effort입니다.
- **미국 뉴스 번역**: 영어 헤드라인을 무료 Google 번역(gtx)으로 `한글(영어)` 병기합니다. 실패 시 원문만 표시.
- **카톡 링크 도메인**: 카카오는 메시지 링크를 '등록된 Web 플랫폼 사이트 도메인'으로만 허용합니다.
  링크(모바일 네이버 증시 `m.stock.naver.com`)가 정상 동작하려면 **앱 > 플랫폼(Web) 사이트 도메인에
  `https://m.stock.naver.com` 추가** 하세요. 미등록 시 링크가 localhost 등으로 대체됩니다.
  (참고: 카톡 메시지 본문 자체가 브리핑 전문이므로 링크는 보조 용도입니다.)
- **정확도**: 데이터가 쌓이면 `analyze.py` 의 가중치(`fscore`, `BETA` 등)를 실제 적중과 비교해
  튜닝할 수 있습니다. 과최적화를 피하려 규칙은 단순하게 유지했습니다.
