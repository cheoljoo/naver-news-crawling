"""네이버 검색 API로 검색한다 (뉴스/블로그/카페/웹문서/지역/오타변환/이미지).

사용 예:
    uv run search_news.py "삼성전자"                          # 기본은 뉴스
    uv run search_news.py "반도체" "HBM" --pages 3 --out out/news.jsonl
    uv run search_news.py "맛집" --type blog --sort sim
    uv run search_news.py "고양이" --type image --filter large
    uv run search_news.py "강남역 카페" --type local
    uv run search_news.py "spdlqj" --type errata              # 자판 오입력 교정

인증: 환경변수 또는 .env 의 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET (두 키만 읽는다).
한계: display 최대 100, start 최대 1000 → 키워드당 최대 1,000건 (지역은 display 5, 1페이지).
      본문/이미지 파일 자체는 제공되지 않고 주소만 제공된다.
"""
import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime
from pathlib import Path

import usage

# hub: NAVER API HUB(네이버 클라우드). 2026-07-31 이후 신규 신청은 여기서만 가능.
# legacy: 예전 개발자센터 방식(2027-06-30 지원 종료 예정, 기존 키 보유자만 사용 가능).
BACKENDS = {
    "hub": {
        "url": "https://naverapihub.apigw.ntruss.com/search/v1/{path}",
        "id_header": "X-NCP-APIGW-API-KEY-ID",
        "secret_header": "X-NCP-APIGW-API-KEY",
    },
    "legacy": {
        "url": "https://openapi.naver.com/v1/search/{path}.json",
        "id_header": "X-Naver-Client-Id",
        "secret_header": "X-Naver-Client-Secret",
    },
}

# 종류별 명세 (공식 문서 기준).
#   sorts/sort_default: 허용 정렬값과 기본 사용값 (None이면 sort 파라미터 없음)
#   max_display/max_start: display/start 상한. paged=False면 query만 보냄(오타변환)
TYPES = {
    "news": dict(path="news", label="뉴스", sorts=("sim", "date"), sort_default="date",
                 max_display=100, max_start=1000,
                 fields=("title", "description", "originallink", "link", "pubDate")),
    "blog": dict(path="blog", label="블로그", sorts=("sim", "date"), sort_default="date",
                 max_display=100, max_start=1000,
                 fields=("title", "description", "link", "bloggername", "bloggerlink", "postdate")),
    "cafe": dict(path="cafearticle", label="카페글", sorts=("sim", "date"), sort_default="date",
                 max_display=100, max_start=1000,
                 fields=("title", "description", "link", "cafename", "cafeurl")),
    "web": dict(path="webkr", label="웹문서", sorts=None, sort_default=None,
                max_display=100, max_start=1000,
                fields=("title", "description", "link")),
    "image": dict(path="image", label="이미지", sorts=("sim", "date"), sort_default="date",
                  max_display=100, max_start=1000,
                  fields=("title", "link", "thumbnail", "sizeheight", "sizewidth")),
    "local": dict(path="local", label="지역", sorts=("random", "comment"), sort_default="random",
                  max_display=5, max_start=1,
                  fields=("title", "category", "description", "link", "telephone",
                          "address", "roadAddress", "mapx", "mapy")),
    "errata": dict(path="errata", label="오타변환", sorts=None, sort_default=None,
                   max_display=1, max_start=1, paged=False, fields=("errata",)),
}

LINE = {  # 화면 출력 형식
    "news": lambda it: f"[{it['pubDate'][:16]}] {it['title']}\n  {it['link']}",
    "blog": lambda it: f"[{it['postdate']}] {it['title']} ({it['bloggername']})\n  {it['link']}",
    "cafe": lambda it: f"{it['title']} ({it['cafename']})\n  {it['link']}",
    "web": lambda it: f"{it['title']}\n  {it['link']}",
    "image": lambda it: f"[{it['sizewidth']}x{it['sizeheight']}] {it['title']}\n  {it['link']}",
    "local": lambda it: f"{it['title']} [{it['category']}] {it['roadAddress'] or it['address']}\n  {it['link']}",
    "errata": lambda it: f"{it['query']} -> {it['errata'] or '(교정할 오타 없음)'}",
}

WANTED_KEYS = ("NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET")
TAG_RE = re.compile(r"</?b>")


def load_credentials() -> tuple[str, str]:
    """환경변수 우선, 없으면 .env에서 NAVER_CLIENT_* 두 키만 읽는다."""
    values = {k: os.environ.get(k, "") for k in WANTED_KEYS}
    env_file = Path(__file__).with_name(".env")
    if env_file.exists() and not all(values.values()):
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if key in WANTED_KEYS and not values[key]:
                values[key] = val.strip().strip("'\"")
    missing = [k for k, v in values.items() if not v]
    if missing:
        sys.exit(f"오류: {', '.join(missing)} 값이 없습니다 (.env 또는 환경변수 확인)")
    return values["NAVER_CLIENT_ID"], values["NAVER_CLIENT_SECRET"]


def clean(text: str) -> str:
    return html.unescape(TAG_RE.sub("", text))


def request_json(req: urllib.request.Request, hint_scope: str, backend: str,
                 group: str = "search") -> dict:
    """공통 요청 + 재시도 + 오류 힌트 + 사용량 기록. (데이터랩 스크립트도 재사용)"""
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.load(resp)
            usage.record(group)  # 성공 호출만 센다
            return data
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:200]
            if e.code == 429 and attempt < 2:  # 호출 한도/속도 초과 → 잠시 후 재시도
                time.sleep(1 + attempt)
                continue
            hints = {401: f"Client ID/Secret 확인 (현재 backend={backend}; 키 종류와 backend가 맞아야 함)",
                     403: f"앱에 '{hint_scope}' API 권한이 있는지 확인", 429: "호출 한도 초과"}
            sys.exit(f"HTTP {e.code} ({hints.get(e.code, '요청 오류')}): {detail}")
        except urllib.error.URLError as e:
            if attempt < 2:
                time.sleep(1 + attempt)
                continue
            sys.exit(f"네트워크 오류: {e.reason}")
    return {}


def fetch_page(kind: str, params: dict, cid: str, secret: str, backend: str) -> dict:
    be = BACKENDS[backend]
    url = be["url"].format(path=TYPES[kind]["path"]) + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url, headers={be["id_header"]: cid, be["secret_header"]: secret})
    return request_json(req, f"검색 > {TYPES[kind]['label']}", backend)


def normalize(it: dict, query: str, kind: str) -> dict:
    out = {"query": query}
    for f in TYPES[kind]["fields"]:
        v = it.get(f, "")
        if f in ("title", "description") and isinstance(v, str):
            v = clean(v)
        elif f == "pubDate":
            try:
                v = parsedate_to_datetime(v).isoformat()
            except (ValueError, TypeError):
                pass
        out[f] = v
    return out


def search(query: str, pages: int, display: int, sort: str | None, cid: str, secret: str,
           backend: str = "hub", kind: str = "news", img_filter: str = "all") -> list[dict]:
    spec = TYPES[kind]
    if spec.get("paged", True) is False:  # 오타변환: query만 보내고 1번 호출
        data = fetch_page(kind, {"query": query}, cid, secret, backend)
        return [normalize(data, query, kind)]
    items: list[dict] = []
    for page in range(pages):
        start = page * display + 1
        if start > spec["max_start"]:  # API 상한
            break
        params = {"query": query, "display": display, "start": start}
        if sort:
            params["sort"] = sort
        if kind == "image":
            params["filter"] = img_filter  # all | large | medium | small (이미지 전용)
        data = fetch_page(kind, params, cid, secret, backend)
        batch = data.get("items", [])
        items.extend(normalize(it, query, kind) for it in batch)
        if len(batch) < display or start + display > data.get("total", 0):
            break
        time.sleep(0.1)  # 예의상 간격
    return items


def dedupe_key(kind: str, it: dict):
    if kind == "news":
        return it["originallink"] or it["link"]
    if kind == "local":
        return (it["title"], it["roadAddress"] or it["address"])
    return it.get("link") or id(it)  # errata 등 링크 없는 결과는 중복 제거 안 함


def main() -> None:
    ap = argparse.ArgumentParser(description="네이버 검색 API (뉴스/블로그/카페/웹문서/지역/오타변환/이미지)")
    ap.add_argument("queries", nargs="+", help="검색어 (여러 개 가능)")
    ap.add_argument("--type", choices=list(TYPES), default="news", help="검색 종류 (기본 news)")
    ap.add_argument("--pages", type=int, default=1, help="키워드당 페이지 수 (기본 1)")
    ap.add_argument("--display", type=int, default=None,
                    help="페이지당 건수 (기본: 종류별 최대. 지역은 1~5, 나머지 1~100)")
    ap.add_argument("--sort", default=None,
                    help="정렬 (뉴스/블로그/카페/이미지: sim|date, 지역: random|comment, 웹문서/오타변환: 없음)")
    ap.add_argument("--filter", choices=["all", "large", "medium", "small"], default="all",
                    help="이미지 크기 필터 (--type image 에서만 사용)")
    ap.add_argument("--backend", choices=list(BACKENDS), default="hub",
                    help="hub=NAVER API HUB(신규 키, 기본), legacy=예전 개발자센터 키")
    ap.add_argument("--out", help="JSONL 저장 경로 (생략하면 화면에 출력)")
    ap.add_argument("--format", choices=["text", "json"], default="text",
                    help="화면 출력 형식 (기본 text)")
    ap.add_argument("--no-usage", action="store_true", help="끝에 사용량 요약을 출력하지 않음")
    args = ap.parse_args()

    spec = TYPES[args.type]
    display = args.display if args.display is not None else spec["max_display"]
    if not 1 <= display <= spec["max_display"]:
        ap.error(f"--display 는 {args.type} 에서 1~{spec['max_display']}")
    sort = args.sort if args.sort is not None else spec["sort_default"]
    if spec["sorts"] is None:
        if args.sort is not None:
            ap.error(f"{args.type} 검색은 --sort 를 지원하지 않습니다")
        sort = None
    elif sort not in spec["sorts"]:
        ap.error(f"{args.type} 의 --sort 는 {'|'.join(spec['sorts'])}")

    cid, secret = load_credentials()
    seen: set = set()
    results: list[dict] = []
    for q in args.queries:
        for it in search(q, args.pages, display, sort, cid, secret,
                         args.backend, args.type, args.filter):
            key = dedupe_key(args.type, it)
            if key in seen:
                continue
            seen.add(key)
            results.append(it)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as f:
            for it in results:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
        print(f"{len(results)}건 저장: {out}")
    elif args.format == "json":
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for it in results:
            print(LINE[args.type](it))
        print(f"\n총 {len(results)}건 (중복 제거 후)", file=sys.stderr)

    if not args.no_usage:  # 표준 출력(JSON 등)을 깨지 않도록 stderr로 출력
        usage.print_summary(["search"])


if __name__ == "__main__":
    main()
