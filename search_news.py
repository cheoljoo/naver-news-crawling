"""네이버 검색 API(뉴스)로 기사를 검색한다.

사용 예:
    uv run search_news.py "삼성전자"
    uv run search_news.py "반도체" "HBM" --pages 3 --sort date --out out/news.jsonl
    uv run search_news.py "AI" --format json

인증: 환경변수 또는 .env 의 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET (두 키만 읽는다).
한계: display 최대 100, start 최대 1000 → 키워드당 최대 1,000건. 본문은 제공되지 않는다.
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

# hub: NAVER API HUB(네이버 클라우드). 2026-07-31 이후 신규 신청은 여기서만 가능.
# legacy: 예전 개발자센터 방식(2027-06-30 지원 종료 예정, 기존 키 보유자만 사용 가능).
BACKENDS = {
    "hub": {
        "url": "https://naverapihub.apigw.ntruss.com/search/v1/news",
        "id_header": "X-NCP-APIGW-API-KEY-ID",
        "secret_header": "X-NCP-APIGW-API-KEY",
    },
    "legacy": {
        "url": "https://openapi.naver.com/v1/search/news.json",
        "id_header": "X-Naver-Client-Id",
        "secret_header": "X-Naver-Client-Secret",
    },
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


def fetch_page(query: str, start: int, display: int, sort: str,
               cid: str, secret: str, backend: str = "hub") -> dict:
    be = BACKENDS[backend]
    params = urllib.parse.urlencode(
        {"query": query, "display": display, "start": start, "sort": sort})
    req = urllib.request.Request(
        f"{be['url']}?{params}",
        headers={be["id_header"]: cid, be["secret_header"]: secret})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:200]
            if e.code == 429 and attempt < 2:  # 호출 한도/속도 초과 → 잠시 후 재시도
                time.sleep(1 + attempt)
                continue
            hints = {401: f"Client ID/Secret 확인 (현재 backend={backend}; 키 종류와 backend가 맞아야 함)",
                     403: "앱에 '검색 > 뉴스' 권한이 있는지 확인", 429: "호출 한도 초과"}
            sys.exit(f"HTTP {e.code} ({hints.get(e.code, '요청 오류')}): {detail}")
        except urllib.error.URLError as e:
            if attempt < 2:
                time.sleep(1 + attempt)
                continue
            sys.exit(f"네트워크 오류: {e.reason}")
    return {}


def search(query: str, pages: int, display: int, sort: str,
           cid: str, secret: str, backend: str = "hub") -> list[dict]:
    items: list[dict] = []
    for page in range(pages):
        start = page * display + 1
        if start > 1000:  # API 상한
            break
        data = fetch_page(query, start, display, sort, cid, secret, backend)
        batch = data.get("items", [])
        for it in batch:
            try:
                pub = parsedate_to_datetime(it["pubDate"]).isoformat()
            except (KeyError, ValueError, TypeError):
                pub = it.get("pubDate", "")
            items.append({
                "query": query,
                "title": clean(it.get("title", "")),
                "description": clean(it.get("description", "")),
                "originallink": it.get("originallink", ""),
                "link": it.get("link", ""),
                "pubDate": pub,
            })
        if len(batch) < display or start + display > data.get("total", 0):
            break
        time.sleep(0.1)  # 예의상 간격
    return items


def main() -> None:
    ap = argparse.ArgumentParser(description="네이버 뉴스 검색 (검색 API)")
    ap.add_argument("queries", nargs="+", help="검색어 (여러 개 가능)")
    ap.add_argument("--pages", type=int, default=1, help="키워드당 페이지 수 (기본 1)")
    ap.add_argument("--display", type=int, default=100, help="페이지당 건수 1~100 (기본 100)")
    ap.add_argument("--sort", choices=["sim", "date"], default="date",
                    help="sim=정확도순, date=최신순 (기본 date)")
    ap.add_argument("--backend", choices=list(BACKENDS), default="hub",
                    help="hub=NAVER API HUB(신규 키, 기본), legacy=예전 개발자센터 키")
    ap.add_argument("--out", help="JSONL 저장 경로 (생략하면 화면에 출력)")
    ap.add_argument("--format", choices=["text", "json"], default="text",
                    help="화면 출력 형식 (기본 text)")
    args = ap.parse_args()
    if not 1 <= args.display <= 100:
        ap.error("--display 는 1~100")

    cid, secret = load_credentials()
    seen: set[str] = set()
    results: list[dict] = []
    for q in args.queries:
        for it in search(q, args.pages, args.display, args.sort, cid, secret,
                         args.backend):
            key = it["originallink"] or it["link"]
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
            print(f"[{it['pubDate'][:16]}] {it['title']}\n  {it['link']}")
        print(f"\n총 {len(results)}건 (중복 제거 후)", file=sys.stderr)


if __name__ == "__main__":
    main()
