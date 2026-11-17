# naver-news-crawling

네이버 **검색 API(뉴스·블로그·카페글·웹문서·지역·오타변환·이미지)** 와 **데이터랩(검색어 트렌드·쇼핑인사이트)** 를
호출해 화면에 출력하거나 JSONL/JSON으로 저장하는 작은 CLI 도구입니다.
외부 패키지 없이 Python 표준 라이브러리만 사용하며, [`uv`](https://docs.astral.sh/uv/)로 실행합니다.

> 이 문서는 개발 과정에서 확인한 내용(키 발급 방법, 2026년 API 이관 이슈, 오류 해결 기록)을 모두 담고 있습니다.
> 조사 시점은 **2026-11-16**이며, 요금·한도는 이후 바뀔 수 있습니다.

---

## 1. 빠른 시작

```bash
# 1) 키 발급 (아래 3절 참고) 후 .env 작성
cp .env.example .env          # 또는 make env
#   NAVER_CLIENT_ID=...
#   NAVER_CLIENT_SECRET=...

# 2) 실행
make news Q='삼성전자' DISPLAY=5
# 또는
uv run search_news.py "삼성전자" --display 5
```

## 2. 사용법

### 2.1 지원 기능 한눈에 보기

| 기능 | make 명령 | 직접 실행 | API 경로 (`https://naverapihub.apigw.ntruss.com` 뒤) |
|---|---|---|---|
| 뉴스 | `make news` | `search_news.py --type news` (기본) | `GET /search/v1/news` |
| 블로그 | `make blog` | `--type blog` | `GET /search/v1/blog` |
| 카페글 | `make cafe` | `--type cafe` | `GET /search/v1/cafearticle` |
| 웹문서 | `make web` | `--type web` | `GET /search/v1/webkr` |
| 이미지 | `make image` | `--type image` | `GET /search/v1/image` |
| 지역 | `make local` | `--type local` | `GET /search/v1/local` |
| 오타변환 | `make errata` | `--type errata` | `GET /search/v1/errata` |
| 검색어 트렌드 | `make trend` | `naver_datalab.py trend` | `POST /search-trend/v1/search` |
| 쇼핑인사이트 | `make shopping` | `naver_datalab.py shopping` | `POST /shopping/v1/...` (8종, 2.3절) |

- **`make search`는 뉴스 전용이 아니라 범용입니다.** `make search Q='맛집' TYPE=blog`처럼 `TYPE`으로 종류를 고르며,
  `TYPE`을 생략하면 뉴스입니다. `make news`, `make blog` 등은 `TYPE`을 미리 지정한 단축 명령입니다.
- 검색 계열 7종은 한 키(Application)로 모두 쓸 수 있고, 호출 한도를 함께 씁니다(아래 "사용량 확인").

### 2.2 검색 API (`search_news.py`)

```bash
uv run search_news.py "키워드"                                       # 뉴스 최신순 100건 출력
uv run search_news.py "반도체" "HBM" --pages 3 --out out/news.jsonl   # 여러 키워드 → JSONL 저장
uv run search_news.py "맛집" --type blog --sort sim                   # 블로그 정확도순
uv run search_news.py "고양이" --type image --filter large            # 큰 이미지만
uv run search_news.py "강남역 카페" --type local                      # 지역(업체/장소) 검색
uv run search_news.py "spdlqj" --type errata                          # spdlqj -> 네이버
uv run search_news.py "키워드" --backend legacy                       # 예전 개발자센터 키 (4절 참고)
```

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `queries` | (필수) | 검색어. 여러 개 가능 (공백이 든 키워드는 따옴표로) |
| `--type` | `news` | `news` `blog` `cafe` `web` `image` `local` `errata` |
| `--pages` | 1 | 키워드당 페이지 수 (**페이지 1번 = 호출 1회**) |
| `--display` | 종류별 최대 | 페이지당 건수. 지역은 1~5, 나머지는 1~100 |
| `--sort` | 종류별 | 아래 표 참고. 지원하지 않는 종류에 지정하면 오류 |
| `--filter` | `all` | 이미지 크기 `all` `large` `medium` `small` (`--type image`에서만 사용) |
| `--backend` | `hub` | `hub`=NAVER API HUB(신규 키), `legacy`=예전 개발자센터 키 |
| `--out` | (없음) | 지정하면 JSONL 파일로 저장, 없으면 화면 출력 |
| `--format` | `text` | 화면 출력 형식 `text` / `json` |

**종류별 차이** (공식 문서 기준)

| type | display | start | sort (이 도구의 기본) | 저장 필드 |
|---|---|---|---|---|
| `news` | 1~100 | 1~1000 | `sim`\|`date` (`date`) | `title` `description` `originallink` `link` `pubDate` |
| `blog` | 1~100 | 1~1000 | `sim`\|`date` (`date`) | `title` `description` `link` `bloggername` `bloggerlink` `postdate` |
| `cafe` | 1~100 | 1~1000 | `sim`\|`date` (`date`) | `title` `description` `link` `cafename` `cafeurl` |
| `web` | 1~100 | 1~1000 | 없음 | `title` `description` `link` |
| `image` | 1~100 | 1~1000 | `sim`\|`date` (`date`) + `--filter` | `title` `link` `thumbnail` `sizeheight` `sizewidth` |
| `local` | **1~5** | 1 (1페이지뿐) | `random`\|`comment` (`random`) | `title` `category` `description` `link` `telephone` `address` `roadAddress` `mapx` `mapy` |
| `errata` | - | - | 없음 (`query`만 전송) | `errata` |

- 모든 저장 행에 `query`(검색어)가 함께 들어갑니다.
- API 자체의 `sort` 기본값은 `sim`이지만, 이 도구는 최신 자료를 보기 위해 `date`를 기본으로 합니다(해당되는 종류만).
- `image`의 `title`은 이미지가 실린 문서의 제목, `link`는 이미지 원본 주소입니다. 이미지 파일 자체가 아니라 **주소만** 줍니다.
  파일의 저작권은 각 게시자에게 있으니 재사용 전에 이용 조건을 확인하세요.
- `local`의 `telephone`은 하위 호환용 필드라 값이 비어 있고, `link`가 빈 업체도 있습니다.
  `mapx`/`mapy`는 좌표(WGS84)입니다. `sort=comment`는 카페·블로그 리뷰 개수순입니다.
- `errata`는 한/영 자판을 잘못 친 검색어를 교정합니다(교정할 게 없으면 빈 문자열).
- `--backend legacy`의 종류별 주소(`.../v1/search/<type>.json`)는 뉴스 규칙에서 유추한 것으로, **뉴스 외에는 실제 호출로 확인하지 못했습니다.**

### 2.3 데이터랩 (`naver_datalab.py`)

두 기능 모두 `POST` + JSON 본문이며, 검색 API와 같은 키를 씁니다(HUB 전용). 결과의 `ratio`는 조회 구간 내
**최대값을 100으로 한 상대값**이라 절대 검색량이 아닙니다.

**검색어 트렌드** — 검색어를 최대 5그룹까지 비교합니다.
```bash
uv run naver_datalab.py trend "AI" "반도체" --start 2026-01-01 --unit month     # 검색어마다 한 그룹
uv run naver_datalab.py trend --group "AI:AI,인공지능" --group "반도체:반도체,HBM" --days 90
make trend Q='AI 반도체' START=2026-01-01 UNIT=month
```
- 그룹당 검색어는 최대 20개, 시작일은 2016-01-01 이후입니다.
- 필터: `--device pc|mo`, `--gender m|f`, `--ages 1,2,...` (1=0~12세, 2=13~18, 3=19~24, 4=25~29, 5=30~34,
  6=35~39, 7=40~44, 8=45~49, 9=50~54, 10=55~59, 11=60세 이상). 생략하면 전체입니다.

**쇼핑인사이트** — `--mode`로 8종 중 하나를 고릅니다. 시작일은 2017-08-01 이후입니다.

| `--mode` | 의미 | 필요한 입력 |
|---|---|---|
| `categories` | 분야별 트렌드 | `--category '이름=코드1,코드2'` (최대 3개) |
| `device` / `gender` / `age` | 분야의 기기별 / 성별 / 연령별 | `--category 코드` |
| `keywords` | 키워드별 트렌드 | `--category 코드` + `--keyword '그룹이름=검색어'` (최대 5개, 그룹당 검색어 1개) |
| `keyword-device` / `keyword-gender` / `keyword-age` | 키워드의 기기별 / 성별 / 연령별 | `--category 코드` + `--keyword 검색어` |

```bash
uv run naver_datalab.py shopping --mode categories --category "패션의류=50000000" --unit month
uv run naver_datalab.py shopping --mode keyword-age --category 50000000 --keyword 정장 --days 60
make shopping MODE=keywords CATEGORY=50000000 KEYWORD='정장=정장' UNIT=month
```
- 분야 코드는 네이버쇼핑 URL의 `cat_id` 값입니다 (예: 패션의류 `50000000`).
- 연령 코드는 `10`(10~19세), `20`, `30`, `40`, `50`, `60`(60세 이상)입니다.
- 결과 축과 겹치는 필터(`device`=기기별, `gender`=성별, `age`=연령별 모드)는 요청에서 자동으로 뺍니다. 문서 예시가 그렇게 되어 있어서 따랐습니다.
- 출력은 기본 표(text)이고, `--format json`은 원본 JSON, `--out 경로`는 원본 JSON 저장입니다.
- **검증 범위**: 실제 호출로 `trend`, `categories`, `device`, `keywords`, `keyword-age`를 확인했습니다.
  `gender`, `age`, `keyword-device`, `keyword-gender`는 명세대로 구현했지만 호출해 보지 않았습니다.

### 2.4 Makefile

`make help`로 목록을 볼 수 있습니다.

| 명령 | 동작 |
|---|---|
| `make env` | `.env`가 없을 때만 `.env.example`을 복사 |
| `make check-env` | 키 설정 여부만 확인 (값은 출력하지 않음) |
| `make search Q='...' [TYPE=...]` | 범용 검색 (`TYPE` 생략 시 뉴스) |
| `make news` `blog` `cafe` `web` `local` `errata` `image` | 종류별 단축 (`Q` 필수) |
| `make save Q='...' [TYPE=...]` | 검색 결과를 JSONL로 저장 (기본 `out/<TYPE>.jsonl`, `OUT=`로 변경) |
| `make trend Q='A B'` | 데이터랩 검색어 트렌드 |
| `make shopping MODE=... CATEGORY=... [KEYWORD=...]` | 데이터랩 쇼핑인사이트 |
| `make usage` | 사용량 보기 (이 도구가 보낸 호출 기준, API 호출 없음) |
| `make usage-set GROUP=search DAY=120 MONTH=3400` | 콘솔에서 읽은 값으로 시작값 맞추기 (`GROUP`=`search`\|`trend`\|`shopping`) |
| `make check` | 문법·CLI 검사 (API 호출 없음) |
| `make clean` | `out/`와 `__pycache__` 삭제 |

검색·데이터랩 명령은 **끝에 사용량 요약이 자동으로 붙습니다**(아래 "사용량 자동 표시"). 끄려면 `ARGS=--no-usage`를 붙입니다.

변수: `Q`(검색어, 공백 구분·여러 단어는 따옴표), `TYPE`, `PAGES`(기본 1), `DISPLAY`, `SORT`, `FILTER`, `BACKEND`, `OUT`,
데이터랩용 `START` `END` `DAYS` `UNIT` `DEVICE` `GENDER` `AGES` `MODE` `CATEGORY` `KEYWORD`, 그리고 스크립트에 그대로
넘기는 `ARGS`. `DISPLAY`와 `SORT`는 종류마다 허용 범위가 달라 **지정할 때만** 전달합니다.

```bash
make news  Q='반도체 HBM' PAGES=3                    # 키워드 2개 (각 3페이지)
make news  Q='"삼성 전자"' SORT=sim                  # 공백이 든 키워드 하나
make blog  Q='맛집' SORT=sim
make search Q='고양이' TYPE=image FILTER=large
make local Q='"강남역 카페"'
make errata Q='spdlqj'
make save  Q='AI' TYPE=cafe PAGES=5                  # out/cafe.jsonl
make trend Q='AI 반도체' START=2026-01-01 UNIT=month
make shopping MODE=categories CATEGORY='패션의류=50000000' UNIT=month
```

### 2.5 결과 예시

2026-11-17에 실제로 호출한 결과의 **모양**입니다. 값은 길이를 줄이고(`…`) 제3자 식별 정보(블로그 ID, 카페 이름 등)는 익명화했습니다.

**출력 방식 세 가지**
- 기본(`text`): 결과를 한 건씩 출력하고, 맨 끝의 `총 N건 (중복 제거 후)`와 **사용량 요약**은 **표준 오류(stderr)** 로 나갑니다
  (그래서 `--format json > 파일`로 저장해도 JSON이 깨지지 않습니다). 사용량 요약은 아래 예시에서는 생략했습니다.
- `--format json`: 결과 전체를 **JSON 배열**로 출력합니다.
- `--out 파일`: **JSONL**(한 줄에 객체 하나, 배열 아님)로 저장하고 `N건 저장: 파일`만 출력합니다. 덮어쓰기입니다.

#### 뉴스 (`make news Q='커피' DISPLAY=2`)
```text
[2026-11-17T18:00] [돋보기] 햇반·비비고만 있지 않다…'생분해 바이오' 리더십 키우는 CJ...
  https://www.example-news.com/news/articleView.html?idxno=000001
[2026-11-17T17:54] 커피 전문점 …
  https://n.news.naver.com/mnews/article/000/0000000000?sid=101

총 2건 (중복 제거 후)
```
```json
{"query": "커피", "title": "[돋보기] 햇반·비비고만 …", "description": "올 초에는 카페 브랜드 … 협업을 통해 'PHA 빨대'로 …",
 "originallink": "https://www.example-news.com/news/articleView.html?idxno=000001",
 "link": "https://www.example-news.com/news/articleView.html?idxno=000001",
 "pubDate": "2026-11-17T18:00:00+09:00"}
```
- 줄 맨 앞 `[ ]`는 발행 시각(분 단위)입니다. 네이버에 없는 기사는 `link`가 원문 주소와 같습니다.

#### 블로그 (`make blog Q='커피'`)
```text
[20261117] 발리자유여행 / 르네상스 울루와뚜 리조트 (블로거 이름)
  https://blog.naver.com/<블로그ID>/<글번호>
```
```json
{"query": "커피", "title": "발리자유여행 / 르네상스 울루와뚜 리조트", "description": "있고 커피 머신이 있긴 하지만 … ",
 "link": "https://blog.naver.com/<블로그ID>/<글번호>",
 "bloggername": "블로거 이름", "bloggerlink": "https://blog.naver.com/<블로그ID>", "postdate": "20261117"}
```
- `postdate`는 `YYYYMMDD` 문자열 그대로이고 시각은 없습니다.

#### 카페글 (`make cafe Q='커피'`)
```text
비오는날 카페라떼중독..ㅠㅠ (카페 이름)
  https://cafe.naver.com/<카페주소>/<글번호>
```
```json
{"query": "커피", "title": "비오는날 카페라떼중독..ㅠㅠ", "description": "1일 1라떼..중독 비오는날 마시니 …",
 "link": "https://cafe.naver.com/<카페주소>/<글번호>", "cafename": "카페 이름", "cafeurl": "https://cafe.naver.com/<카페주소>"}
```
- 날짜 필드가 없습니다(카페글 응답에는 작성일이 없음).

#### 웹문서 (`make web Q='커피'`)
```text
커피 - 나무위키
  https://namu.wiki/w/%EC%BB%A4%ED%94%BC
```
```json
{"query": "커피", "title": "커피 - 나무위키", "description": "Coffee 커피나무 열매의 씨앗(원두)을 볶아 향을 내고, …",
 "link": "https://namu.wiki/w/%EC%BB%A4%ED%94%BC"}
```
- 필드가 가장 적습니다. 날짜도 정렬 옵션도 없습니다.

#### 이미지 (`make image Q='커피' FILTER=large`)
```text
[600x600] 25ml 나무 손잡이 스테인리스 스틸 커피 스쿱 … : 상점이름
  http://shopN.phinf.naver.net/20261117_148/…_JPEG/….jpg
```
```json
{"query": "커피", "title": "25ml 나무 손잡이 스테인리스 스틸 커피 스쿱 … : 상점이름",
 "link": "http://shopN.phinf.naver.net/20261117_148/…_JPEG/….jpg",
 "thumbnail": "https://search.pstatic.net/common/?type=b150&src=http%3A%2F%2Fshop1.phinf.naver.net%2F…",
 "sizeheight": "600", "sizewidth": "600"}
```
- 줄 맨 앞 `[가로x세로]`는 픽셀 크기입니다. `sizeheight`/`sizewidth`는 **숫자가 아니라 문자열**입니다.
- 쇼핑 상품 이미지가 많이 섞여 나옵니다. 이미지 주소는 `http://`로 오는 경우도 있습니다.

#### 지역 (`make local Q='"강남역 카페"'`, 최대 5건)
```text
OO카페 강남점 [카페,디저트>케이크전문] 서울특별시 강남구 테헤란로8길 44 1층
  https://www.instagram.com/<계정>
```
```json
{"query": "강남역 카페", "title": "OO카페 강남점", "category": "카페,디저트>케이크전문", "description": "",
 "link": "https://www.instagram.com/<계정>", "telephone": "",
 "address": "서울특별시 강남구 역삼동 827-66 1층", "roadAddress": "서울특별시 강남구 테헤란로8길 44 1층",
 "mapx": "1270323194", "mapy": "374960379"}
```
- `mapx`/`mapy`는 **10,000,000을 곱한 정수 문자열**입니다. 나누면 경도 127.0323194, 위도 37.4960379가 되어 강남역 부근과 맞습니다.
  (문서에는 WGS84 좌표라고만 적혀 있어, 이 변환은 실제 값으로 확인한 것입니다.)
- `telephone`과 `description`은 비어 있고, `link`는 업체가 등록한 주소라 인스타그램 등 제각각이며 빈 값일 수도 있습니다.
- 출력 줄은 `이름 [분류] 도로명주소`이고, 도로명주소가 없으면 지번주소를 보여줍니다.

#### 오타변환 (`make errata Q='spdlqj'`)
```text
spdlqj -> 네이버

총 1건 (중복 제거 후)
```
```json
{"query": "spdlqj", "errata": "네이버"}
```
- 교정할 오타가 없으면 `errata`가 빈 문자열이고 화면에는 `(교정할 오타 없음)`이 나옵니다.

#### 검색어 트렌드 (`make trend Q='AI 반도체' DAYS=40 UNIT=month`)
```text
2026-10-01 ~ 2026-11-17 (month) / ratio: 구간 내 최대=100

■ AI
  2026-10-01  100
  2026-11-01  59.43236

■ 반도체
  2026-10-01  24.94931
  2026-11-01  15.98848
```
`--format json`(또는 `--out`)의 원본은 아래 모양입니다.
```json
{"startDate": "2026-10-01", "endDate": "2026-11-17", "timeUnit": "month",
 "results": [
   {"title": "AI", "keywords": ["AI"],
    "data": [{"period": "2026-10-01", "ratio": 100}, {"period": "2026-11-01", "ratio": 59.43236}]},
   {"title": "반도체", "keywords": ["반도체"],
    "data": [{"period": "2026-10-01", "ratio": 24.94931}, {"period": "2026-11-01", "ratio": 15.98848}]}
 ]}
```
- `period`는 구간의 **시작일**입니다(월 단위면 매월 1일). 마지막 구간은 진행 중이라 값이 작게 나올 수 있습니다.
- `ratio`는 **전체 결과 중 최대값=100**인 상대값이라, 그룹끼리 비교는 되지만 절대 검색량은 알 수 없습니다.

#### 쇼핑인사이트 (`make shopping MODE=device CATEGORY=50000000 DAYS=60 UNIT=month`)
```text
2026-09-01 ~ 2026-11-17 (month) / ratio: 구간 내 최대=100

■ 50000000
  2026-09-01  [mo]  80.26238
  2026-09-01  [pc]  10.58556
  2026-10-01  [mo]  100
  2026-10-01  [pc]  13.45512
```
- 구조는 트렌드와 같고(`results[].title`, `results[].data[].period/ratio`), 기기·성별·연령 모드에서는 각 행에 `group`이 붙습니다.
  `group` 값은 기기별 `pc`/`mo`, 성별 `m`/`f`, 연령별 `10`~`60`입니다(문서 기준. 화면에서 `device`와 `keyword-age`의 `group`을 실제로 확인).
- `categories`는 분야 이름이, `keywords`는 키워드 그룹 이름이 `title`로 나옵니다. 원본 JSON에는 `category` 또는 `keyword` 배열이 더 들어갑니다.
- 분야 코드로 조회하면 `title`이 이름이 아니라 **코드 그대로**(위의 `50000000`) 나옵니다. 이름을 보려면 `categories` 모드에서 `이름=코드`로 지정하세요.

#### 오류가 났을 때
오류는 표준 오류(stderr)에 한 줄로 나오고 종료 코드는 0이 아닙니다. 응답 본문의 앞부분이 함께 나옵니다.
```text
HTTP 401 (Client ID/Secret 확인 (현재 backend=hub; 키 종류와 backend가 맞아야 함)): {"errorMessage":"...","errorCode":"024"}
search_news.py: error: web 검색은 --sort 를 지원하지 않습니다        # 호출 전에 막히는 인자 오류
```

### 동작 특징
- 여러 키워드 결과를 합치면서 **중복을 제거**합니다 (뉴스는 `originallink`(없으면 `link`), 지역은 이름+주소, 나머지는 `link` 기준).
- 제목·요약의 `<b>` 태그와 HTML 엔티티를 제거합니다.
- 뉴스의 `pubDate`를 ISO 8601(`2026-11-16T02:08:00+09:00`)로 변환합니다. 블로그 `postdate`는 `20261117` 형태 그대로입니다.
- 429/네트워크 오류는 최대 3회 재시도합니다. 401/403 등은 원인 힌트와 함께 종료합니다.
- 인증 정보는 환경변수를 우선하고, 없으면 `.env`에서 **`NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` 두 키만** 읽습니다. 값은 어디에도 출력하지 않습니다.

### 저장 형식
`--out`은 JSONL(한 줄에 결과 하나)입니다. 종류별 필드와 실제 모양은 위 **2.5 결과 예시**를 보세요.

### 한계
- API의 `start` 최대값이 1000이라 **키워드당 최대 1,000건**까지만 가져올 수 있습니다 (지역은 1페이지 최대 5건).
- 뉴스·블로그·카페글·웹문서는 **본문이 없고** 요약(`description`)과 주소만 줍니다. 본문이 필요하면 `link`를 따로 수집해야 하며,
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

### 사용량 확인

지금까지 얼마나 호출했는지는 콘솔의 Application 화면에서 볼 수 있습니다.

- **<https://console.ncloud.com/naver-api-hub/application>**
- 목록의 **당일 사용량 / 당월 사용량** 열에 API별 호출 횟수와 한도 대비 %가 표시됩니다(UTC+9, 약 1분 지연, 00:00 KST에 일 사용량 초기화).
- 실제 화면 예시(한 Application에 아래 API가 모두 등록되어 있음):

  | Category | API | 일 한도 | 월 한도 |
  |---|---|---|---|
  | NAVER 검색 | 이미지, 블로그, 지역, 오타변환, 뉴스, 웹문서, 카페 | 25,000회 | 775,000회 |
  | Data Lab | 검색어트렌드, 쇼핑인사이트 | 제한 없음 | 각 50,000회 |

- **검색 계열 API는 한도를 함께 씁니다.** 뉴스·블로그·카페글·웹문서·이미지·지역·오타변환을 섞어 호출해도 하나의 일 25,000회 / 월 775,000회에서 차감됩니다.
- **데이터랩은 별도로 관리됩니다.** 검색어 트렌드와 쇼핑인사이트는 각각 월 50,000회이고 일 한도는 없다고 표시됩니다(요청 1번 = 1회로 보이지만 데이터랩의 차감 방식은 직접 확인하지 못했습니다).
- **요청 1번이 1회입니다.** `--pages 3`이면 키워드당 3회, 키워드 2개면 6회가 차감됩니다
  (실제로 5건 검색 1번 + 3페이지×2키워드 = 7회가 화면의 7/25,000과 일치했습니다).
- 문서끼리 "일 25,000회"와 "월 775,000회"로 서술이 달랐는데, 실제 화면에는 **둘 다 적용**됩니다.
- 목록의 **설정**에서 월·일 한도를 직접 낮추고 사용량 % 알림(이메일/SMS)을 걸 수 있습니다.
  알림은 **통보 대상을 등록해야** 발송됩니다. 무료 기간에는 한도를 늘릴 수는 없습니다.
- 호출 한도를 넘으면 자동 차단되고, 초당 한도(키당 50 RPS)를 넘으면 HTTP 429가 나옵니다.

### 사용량 자동 표시 (이 도구)

**사용량을 읽어 오는 API는 없습니다.** 공식 문서상 사용량·한도는 콘솔에서만 볼 수 있고(당일/당월 사용량 화면, Usage Statistics의 Excel 내려받기),
실제 응답 헤더도 확인해 보니 `X-RateLimit-*` 같은 한도 정보가 없습니다(`x-ncp-trace-id` 등만 옴). 관리용 API도 문서에서 찾지 못했습니다.
그래서 이 도구가 **호출할 때마다 로컬(`.usage.json`)에 횟수를 기록**하고, 검색·데이터랩 명령 끝에 요약을 보여 줍니다.

```text
── 사용량 (이 도구가 이 PC에서 보낸 호출 기준, KST) ──
검색 API  [이번 실행 1회]
  오늘              6 / 25,000 (0.02%)
  이번 달           6 / 775,000 (0.00%)
  ※ 콘솔 기준과 다를 수 있음 (make usage 로 자세히)
```

- `make usage`는 API를 호출하지 않고 전체(검색 / 검색어트렌드 / 쇼핑인사이트)를 보여 줍니다.
- 한도는 콘솔 화면에 표시된 값입니다: 검색 계열은 **일 25,000회 / 월 775,000회**(7종 공유), 데이터랩은 각각 **월 50,000회**(일 한도 없음).
- **"얼마까지가 공짜인가"**: 문서에 무료 제공량 수치는 따로 없습니다. 현재 서비스 전체가 **한시적 무료**이고 유료 전환 시 사전 공지가 나간다고만 안내되어 있어,
  위 한도는 "무료 구간의 끝"이 아니라 **호출 상한**입니다. 유료로 바뀌면 그 기준이 달라질 수 있습니다.
- **정확하지 않을 수 있는 경우**: 이 PC에서 이 도구가 보낸 **성공(HTTP 200) 호출만** 셉니다. 같은 키를 다른 PC·프로그램에서 쓰거나, 콘솔이 오류 호출·재시도를 다르게 세면 어긋납니다.
  날짜 경계는 KST인데, 문서마다 콘솔 기준이 UTC+9/UTC+0로 달라 확인하지 못했습니다. **정확한 값은 항상 콘솔이 기준**입니다.
- **시작값 맞추기**: 이 기능을 쓰기 전에 이미 호출한 분량은 로컬 기록에 없습니다. 콘솔의 당일/당월 값을 읽어 한 번 맞춰 두면 이후부터 거의 맞습니다.
  ```bash
  make usage-set GROUP=search DAY=120 MONTH=3400      # 콘솔의 '당일 사용량'과 '당월 사용량'
  ```
- `.usage.json`은 `.gitignore` 대상이며, 위치는 `USAGE_FILE` 환경변수로 바꿀 수 있습니다. 월이 바뀌면 이번 달 합계는 자동으로 새로 시작합니다.

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
| `search_news.py` | 검색 API CLI: 뉴스·블로그·카페글·웹문서·이미지·지역·오타변환 (표준 라이브러리만 사용) |
| `usage.py` | 호출 횟수 기록과 한도 대비 사용량 표시 (`make usage`, `.usage.json`에 저장) |
| `naver_datalab.py` | 데이터랩 CLI: 검색어 트렌드·쇼핑인사이트 (`search_news.py`의 인증/재시도 코드 재사용) |
| `Makefile` | 자주 쓰는 명령 모음 (`make help`) |
| `.env.example` | 환경변수 템플릿 (빈 값) |
| `README.md` | 이 문서 |

## 8. 참고 자료

공식 문서를 직접 열람하지는 못했고, 아래 3차 자료를 근거로 했습니다. 중요한 값은 공식 문서로 재확인하세요.

- 공식(열람): 검색 API 명세 `https://api.ncloud-docs.com/docs/naver-api-hub-search-<종류>` — `news`, `image`, `blog`, `local`, `errata`, `webkr`, `cafearticle`
  (예: <https://api.ncloud-docs.com/docs/naver-api-hub-search-news>, <https://api.ncloud-docs.com/docs/naver-api-hub-search-image>)
- 공식(열람): 데이터랩 <https://api.ncloud-docs.com/docs/naver-api-hub-search-trend>,
  쇼핑인사이트 `https://api.ncloud-docs.com/docs/naver-api-hub-shopping-insight-<접미사>` (8종, 2.3절의 `--mode`와 대응)
- 공식(열람): <https://guide.ncloud-docs.com/docs/apihub-overview>, <https://guide.ncloud-docs.com/docs/apihub-migration>,
  <https://guide.ncloud-docs.com/docs/apihub-application>, <https://guide.ncloud-docs.com/docs/apihub-spec>
  (일부 페이지는 `stale` 표시가 있고 한도 서술이 서로 달라, 정확한 값은 콘솔 화면이 기준)
- 구형 개발자센터 문서(<https://developers.naver.com/docs/serviceapi/search/news/news.md>)는 열람하지 못했습니다.
- <https://waffleboard.io/blog/naver-search-api-hub-migration-guide>
- <https://keyword-lab-delta.vercel.app/guide/naver-api-hub>
