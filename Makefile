# naver-news-crawling
# 사용법: make help
#
# [검색 API]  make search Q='키워드' TYPE=blog     (TYPE 생략하면 news)
#             단축: make news|blog|cafe|web|local|errata|image Q='키워드'
# [데이터랩]  make trend Q='AI 반도체'              (검색어 트렌드)
#             make shopping MODE=categories CATEGORY='패션의류=50000000'
#
# 공통 변수 (모두 덮어쓸 수 있음)
#   Q        검색어 (공백으로 구분, 여러 단어 키워드는 따옴표로 감싸기)
#   TYPE     news|blog|cafe|web|local|errata|image   (search/save 에서 사용)
#   PAGES    키워드당 페이지 수 (호출 횟수와 같음, 검색 계열은 일 25,000회 공유)
#   DISPLAY  페이지당 건수 (생략하면 종류별 최대: 지역 5, 나머지 100)
#   SORT     news/blog/cafe/image: sim|date, local: random|comment (web/errata는 지정 불가)
#   FILTER   image 크기: all|large|medium|small
#   BACKEND  hub(NAVER API HUB, 기본) | legacy(예전 개발자센터 키)
#   OUT      save 결과 JSONL 경로 (기본 out/<TYPE>.jsonl)
# 데이터랩 변수: START END DAYS UNIT DEVICE GENDER AGES MODE CATEGORY KEYWORD ARGS
#
# 검색/데이터랩 명령은 끝에 사용량(오늘/이번 달, 한도 대비)을 stderr로 보여준다.
#   make usage          전체 사용량 보기 (API 호출 없음)
#   make usage-set ...  콘솔에서 읽은 값으로 시작값 맞추기
#   끄려면 ARGS=--no-usage  (예: make news Q=AI ARGS=--no-usage)

TYPE    ?= news
PAGES   ?= 1
BACKEND ?= hub
OUT     ?= out/$(TYPE).jsonl
UNIT    ?= date
MODE    ?= categories

# 값이 있을 때만 옵션으로 넘긴다 (종류마다 허용 범위가 달라서 고정 기본값을 주지 않음)
SEARCH_OPTS = --pages $(PAGES) --backend $(BACKEND) \
	$(if $(DISPLAY),--display $(DISPLAY)) $(if $(SORT),--sort $(SORT)) $(if $(FILTER),--filter $(FILTER)) $(ARGS)
DL_OPTS = --unit $(UNIT) $(if $(START),--start $(START)) $(if $(END),--end $(END)) \
	$(if $(DAYS),--days $(DAYS)) $(if $(DEVICE),--device $(DEVICE)) $(if $(GENDER),--gender $(GENDER)) \
	$(if $(AGES),--ages $(AGES)) $(ARGS)

SEARCH_TYPES = news blog cafe web local errata image

.DEFAULT_GOAL := help
.PHONY: help env check-env search save $(SEARCH_TYPES) trend shopping usage usage-set check clean

help: ## 사용 가능한 타깃 보기
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | \
		awk -F':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'
	@echo ""
	@echo "예: make news Q='반도체 HBM' PAGES=3"
	@echo "    make blog Q='맛집' SORT=sim"
	@echo "    make search Q='고양이' TYPE=image FILTER=large"
	@echo "    make save Q='AI' TYPE=cafe PAGES=5          # out/cafe.jsonl"
	@echo "    make trend Q='AI 반도체' START=2026-01-01 UNIT=month"
	@echo "    make shopping MODE=categories CATEGORY='패션의류=50000000'"

env: ## .env가 없으면 .env.example을 복사 (있으면 건드리지 않음)
	@if [ -e .env ]; then echo ".env 이미 있음 (변경 안 함)"; \
	else cp .env.example .env && chmod 600 .env && echo ".env 생성됨 - NAVER_CLIENT_ID/SECRET 값을 채우세요"; fi

check-env: ## NAVER_CLIENT_ID/SECRET 설정 여부 확인 (값은 출력하지 않음)
	@for k in NAVER_CLIENT_ID NAVER_CLIENT_SECRET; do \
		v=$$(grep -E "^$$k=" .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d "'\""); \
		if [ -n "$$v" ]; then echo "$$k: 설정됨"; else echo "$$k: 비어 있음 또는 없음"; fail=1; fi; \
	done; [ -z "$$fail" ]

search: ## 범용 검색 (TYPE=news|blog|cafe|web|local|errata|image, 기본 news)
	$(if $(Q),,$(error 검색어가 필요합니다: make search Q='키워드' [TYPE=blog]))
	uv run search_news.py $(Q) --type $(TYPE) $(SEARCH_OPTS)

news: TYPE = news
news: search ## 뉴스 검색

blog: TYPE = blog
blog: search ## 블로그 검색

cafe: TYPE = cafe
cafe: search ## 카페글 검색

web: TYPE = web
web: search ## 웹문서 검색

local: TYPE = local
local: search ## 지역(업체/장소) 검색

errata: TYPE = errata
errata: search ## 오타변환 (한/영 자판 오입력 교정, 예: spdlqj -> 네이버)

image: TYPE = image
image: search ## 이미지 검색 (FILTER=all|large|medium|small)

save: ## 검색 결과를 JSONL로 저장 (TYPE 지정, OUT 기본 out/<TYPE>.jsonl)
	$(if $(Q),,$(error 검색어가 필요합니다: make save Q='키워드' [TYPE=blog]))
	uv run search_news.py $(Q) --type $(TYPE) $(SEARCH_OPTS) --out $(OUT)

trend: ## 데이터랩 검색어 트렌드 (Q=비교할 검색어들, START/END/UNIT/DEVICE/GENDER/AGES)
	$(if $(or $(Q),$(ARGS)),,$(error 검색어가 필요합니다: make trend Q='AI 반도체'))
	uv run naver_datalab.py trend $(Q) $(DL_OPTS)

shopping: ## 데이터랩 쇼핑인사이트 (MODE, CATEGORY, KEYWORD 필요; make help 예시 참고)
	uv run naver_datalab.py shopping --mode $(MODE) \
		$(if $(CATEGORY),--category '$(CATEGORY)') $(if $(KEYWORD),--keyword '$(KEYWORD)') $(DL_OPTS)

usage: ## 사용량 보기 (이 도구가 보낸 호출 기준, API 호출 없음)
	uv run usage.py show

usage-set: ## 콘솔 값으로 시작값 맞추기: make usage-set GROUP=search DAY=120 MONTH=3400
	$(if $(and $(GROUP),$(DAY),$(MONTH)),,$(error GROUP(search|trend|shopping), DAY, MONTH 가 필요합니다))
	uv run usage.py set $(GROUP) --day $(DAY) --month $(MONTH)

check: ## 문법 검사 (API 호출 없음)
	uv run python -c "import ast; [ast.parse(open(f, encoding='utf-8').read()) for f in ('search_news.py', 'naver_datalab.py', 'usage.py')]; print('syntax ok')"
	uv run search_news.py --help >/dev/null && echo "search cli ok"
	uv run naver_datalab.py --help >/dev/null && echo "datalab cli ok"

clean: ## 저장 결과(out/)와 캐시 삭제
	rm -rf out __pycache__
