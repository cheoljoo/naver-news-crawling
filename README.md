# naver-news-crawling

네이버 **뉴스 검색 API**로 기사를 검색해 화면에 출력하거나 JSONL로 저장하는 작은 CLI 도구입니다.
외부 패키지 없이 Python 표준 라이브러리만 사용하며, [`uv`](https://docs.astral.sh/uv/)로 실행합니다.

> 이 문서는 개발 과정에서 확인한 내용(키 발급 방법, 2026년 API 이관 이슈, 오류 해결 기록)을 모두 담고 있습니다.
> 조사 시점은 **2026-11-16**이며, 요금·한도는 이후 바뀔 수 있습니다.

---

## 1. 빠른 시작

```bash
# 1) 키 발급 (아래 3절 참고) 후 .env 작성
cp .env.example .env
#   NAVER_CLIENT_ID=...
#   NAVER_CLIENT_SECRET=...

# 2) 실행
uv run search_news.py "삼성전자" --display 5
```

## 2. 사용법

```bash
uv run search_news.py "키워드"                               # 최신순 100건을 화면에 출력
uv run search_news.py "반도체" "HBM" --pages 3 --out out/news.jsonl   # 여러 키워드 → JSONL 저장
uv run search_news.py "AI" --sort sim --format json          # 정확도순, JSON 출력
uv run search_news.py "키워드" --backend legacy              # 예전 개발자센터 키 사용 (4절 참고)
```

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `queries` | (필수) | 검색어. 여러 개 가능 |
| `--pages` | 1 | 키워드당 가져올 페이지 수 |
| `--display` | 100 | 페이지당 건수 (1~100) |
| `--sort` | `date` | `date`=최신순, `sim`=정확도순 |
| `--backend` | `hub` | `hub`=NAVER API HUB(신규 키), `legacy`=예전 개발자센터 키 |
| `--out` | (없음) | 지정하면 JSONL 파일로 저장, 없으면 화면 출력 |
| `--format` | `text` | 화면 출력 형식 `text` / `json` |

### 동작 특징
- 여러 키워드 결과를 합치면서 `originallink`(없으면 `link`) 기준으로 **중복을 제거**합니다.
- 제목·요약의 `<b>` 태그와 HTML 엔티티를 제거합니다.
- `pubDate`를 ISO 8601(`2026-11-16T02:08:00+09:00`)로 변환합니다.
- 429/네트워크 오류는 최대 3회 재시도합니다. 401/403 등은 원인 힌트와 함께 종료합니다.
- 인증 정보는 환경변수를 우선하고, 없으면 `.env`에서 **`NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` 두 키만** 읽습니다. 값은 어디에도 출력하지 않습니다.

### 저장 형식 (JSONL, 한 줄에 기사 하나)
```json
{"query": "반도체", "title": "...", "description": "...", "originallink": "...", "link": "...", "pubDate": "2026-11-16T02:08:00+09:00"}
```

### 한계
- API의 `start` 최대값이 1000이라 **키워드당 최대 1,000건**까지만 가져올 수 있습니다.
- 응답에 **기사 본문은 없습니다.** 본문이 필요하면 `link`(예: `n.news.naver.com`)를 따로 수집해야 하며,
  이때는 사이트의 robots.txt와 이용약관을 확인하고 요청 간격을 두세요.

---

## 3. API 키 발급 (NAVER API HUB)

### 왜 예전 방식(개발자센터)이 안 되나
- 2026-06-25에 **NAVER API HUB**(네이버 클라우드 플랫폼)가 정식 출시되었습니다.
- **2026-07-31부터 검색 API 신규 신청은 `developers.naver.com`이 아니라 API HUB에서만** 가능합니다.
- 기존 방식의 지원 종료는 2027-06-30로 안내되어 있습니다 (기존 신청자 한정, 쇼핑·책·전문자료 검색은 이관 대상 아님).
- 개발자센터에서 새 앱에 검색 API를 선택하면 `신규로 등록할 수 없는 API가 선택되었습니다`라는 오류가 납니다.

### 발급 절차
1. 네이버 클라우드 플랫폼([ncloud.com](https://www.ncloud.com/))에 가입/로그인해 콘솔에 접속합니다.
   (본인 인증이나 결제 수단 등록을 요구할 수 있습니다.)
2. `Services → Application Service → NAVER API HUB → 이용 신청`에서 약관에 동의합니다.
3. `Application → Application 등록`에서 **NAVER 검색 > 뉴스**를 선택하고 이름을 입력합니다
   (영문·숫자·하이픈 20자 이내, 예: `news-crawler`).
4. 등록한 Application의 **인증 정보**에서 Client ID / Client Secret을 확인해 `.env`에 넣습니다.

> **결제 카드 등록 필요**: NCP 계정에 결제 카드를 등록해야 모든 기능이 활성화됩니다
> (사용자 확인 사항). 카드를 등록하지 않으면 일부 기능이 제한될 수 있으니, 이용 신청이나
> Application 등록이 막히면 콘솔의 결제 수단 등록 상태부터 확인하세요.
> 현재 검색 API는 한시적 무료로 안내되지만 유료 전환 가능성이 있으므로, 카드를 등록했다면
> 콘솔의 사용량과 요금 공지를 가끔 확인하세요.

> NCP IAM 액세스 키(`ncp_iam_...`)는 이 API에서 401이 납니다. 반드시 API HUB Application의
> Client ID/Secret을 사용해야 합니다.

### 호출 방식 비교

| | NAVER API HUB (기본, `--backend hub`) | 예전 개발자센터 (`--backend legacy`) |
|---|---|---|
| URL | `https://naverapihub.apigw.ntruss.com/search/v1/news` | `https://openapi.naver.com/v1/search/news.json` |
| ID 헤더 | `X-NCP-APIGW-API-KEY-ID` | `X-Naver-Client-Id` |
| Secret 헤더 | `X-NCP-APIGW-API-KEY` | `X-Naver-Client-Secret` |
| 쿼리 | `query`, `display`, `start`, `sort` | 동일 |
| 응답 | `lastBuildDate`, `total`, `start`, `display`, `items[]` | 동일 |

`items[]`의 필드는 `title`, `originallink`, `link`, `description`, `pubDate`로 두 방식이 같습니다.
**키만 바꿔서는 안 되고 호출 주소와 헤더가 달라서** 코드가 `--backend`로 둘을 구분합니다.
`start`/`sort`/페이지 넘김이 HUB에서 정상 동작함은 실제 호출로 확인했습니다.

### 한도와 요금
- 자료에 따라 서술이 다릅니다: 검색 API 합산 **월 775,000회**(FAQ), 또는 개별 페이지의 **일 25,000회**.
  API당 키 하나에 50 RPS이며, 초과하면 HTTP 429가 반환됩니다.
- 현재는 한시적 무료로 안내되어 있고 유료 요금제가 추후 공지될 수 있다고 합니다.
- 정확한 값은 콘솔의 Application 사용량과 최신 공지를 확인하세요.

### 오류 형식
- 게이트웨이/인증 오류: `{"error": {"errorCode": "...", "message": "...", "details": "..."}}`
- 파라미터 오류: `{"errorCode": "SE02", "errorMessage": "Invalid display value"}`

---

## 4. 문제 해결 (실제로 겪은 사례)

| 증상 | 원인 | 해결 |
|---|---|---|
| `HTTP 401 ... Scope Status Invalid : Authentication failed. (errorCode 024)` | 개발자센터에서 받은 구형 키에는 검색 API 권한이 없음 (신규 등록이 막혀 있어 저장도 불가) | API HUB에서 새 키를 발급받아 `.env`를 교체 |
| 개발자센터에서 `애플리케이션 설정 실패 / 신규로 등록할 수 없는 API가 선택되었습니다` | 검색 등 이관된 API는 개발자센터에서 신규 등록 불가 | 3절의 API HUB 절차 사용 |
| 새 키인데 401 | 키 종류와 `--backend`가 안 맞음 (HUB 키를 `legacy`로 호출 등) | HUB 키는 기본값, 구형 키만 `--backend legacy` |
| `.env` 값을 읽지 못함 | 키 이름 오타 또는 값 비어 있음 | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` 확인 |
| HTTP 429 | 호출 한도/속도 초과 | 간격을 두고 재시도, 콘솔에서 사용량 확인 |

---

## 5. 키 발급 자동화에 대한 기록

"로그인부터 키 발급까지 자동화할 수 있나?"를 검토한 결과입니다.

- 네이버 개발자센터/NCP 모두 **앱 등록·키 발급용 공개 API가 없습니다.** 웹 UI를 브라우저 자동화로 조작해야 합니다.
- 로그인에는 캡차·2단계 인증이 따르므로 **로그인과 약관 동의는 사람이 직접** 해야 합니다.
  현실적인 방식은 사람이 한 번 로그인하고, 이후 단계만 자동화하는 것입니다.
- 사용한 방법: Docker 기반 [Steel](https://github.com/steel-dev/steel-browser) 브라우저 컨테이너를 띄우고,
  Live View로 사람이 로그인하는 동안 CDP(Chrome DevTools Protocol)로 DOM을 읽고 조작했습니다.
  (디스플레이가 없는 서버에서도 쓸 수 있습니다.)
- 결과적으로 키 발급은 1~2분이면 되는 수동 작업이라 **자동화의 이득이 크지 않습니다.**
  앱을 몇 개 등록하는 정도라면 직접 하는 쪽이 간단합니다. 과도한 자동화는 계정 제재 위험이 있습니다.
- 비밀번호·키는 대화, 로그, 커밋, 명령행 인자에 평문으로 쓰지 말고 `.env`(gitignore)로만 다루세요.

---

## 6. 보안 주의

- `.env`와 `.naver_profile/`은 `.gitignore`에 들어 있습니다. **키를 커밋하지 마세요.**
- `.env.example`에는 빈 값만 있습니다.
- 키가 노출됐다면 콘솔에서 Client Secret을 재발급(폐기)하세요.

## 7. 이 저장소의 파일

| 파일 | 설명 |
|---|---|
| `search_news.py` | 뉴스 검색 CLI (표준 라이브러리만 사용) |
| `.env.example` | 환경변수 템플릿 (빈 값) |
| `README.md` | 이 문서 |

## 8. 참고 자료

공식 문서를 직접 열람하지는 못했고, 아래 3차 자료를 근거로 했습니다. 중요한 값은 공식 문서로 재확인하세요.

- 공식(미열람): <https://api.ncloud-docs.com/docs/naver-api-hub-search-news>
- 공식(미열람): <https://guide.ncloud-docs.com/docs/apihub-overview>, <https://guide.ncloud-docs.com/docs/apihub-migration>
- <https://waffleboard.io/blog/naver-search-api-hub-migration-guide>
- <https://keyword-lab-delta.vercel.app/guide/naver-api-hub>
