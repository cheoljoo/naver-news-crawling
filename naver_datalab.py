"""네이버 데이터랩 (NAVER API HUB): 검색어 트렌드 / 쇼핑인사이트.

사용 예:
    # 검색어 트렌드: 검색어마다 하나의 그룹으로 비교 (최대 5그룹)
    uv run naver_datalab.py trend "AI" "반도체" --start 2026-01-01 --unit month
    uv run naver_datalab.py trend --group "AI:AI,인공지능" --group "반도체:반도체,HBM" --days 90

    # 쇼핑인사이트 (--mode 별로 필요한 입력이 다름)
    uv run naver_datalab.py shopping --mode categories --category "패션의류=50000000"
    uv run naver_datalab.py shopping --mode device --category 50000000
    uv run naver_datalab.py shopping --mode keywords --category 50000000 --keyword "정장=정장"
    uv run naver_datalab.py shopping --mode keyword-age --category 50000000 --keyword 정장

결과의 ratio 는 조회 구간 내 최대값을 100으로 한 **상대값**이다(절대 검색량이 아님).
인증은 search_news.py 와 같은 .env 의 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 을 쓴다 (HUB 전용).
"""
import argparse
import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path

import usage
from search_news import BACKENDS, load_credentials, request_json

HOST = "https://naverapihub.apigw.ntruss.com"
TREND_PATH = "/search-trend/v1/search"
SHOPPING_PATHS = {  # mode -> 경로
    "categories": "/shopping/v1/categories",
    "device": "/shopping/v1/category/device",
    "gender": "/shopping/v1/category/gender",
    "age": "/shopping/v1/category/age",
    "keywords": "/shopping/v1/category/keywords",
    "keyword-device": "/shopping/v1/category/keyword/device",
    "keyword-gender": "/shopping/v1/category/keyword/gender",
    "keyword-age": "/shopping/v1/category/keyword/age",
}
# 모드별로 보내면 안 되는(결과 그룹 축과 겹치는) 필터
DROP = {"device": "device", "gender": "gender", "age": "ages",
        "keyword-device": "device", "keyword-gender": "gender", "keyword-age": "ages"}


def post(path: str, body: dict, cid: str, secret: str, group: str) -> dict:
    be = BACKENDS["hub"]
    req = urllib.request.Request(
        HOST + path, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), method="POST",
        headers={be["id_header"]: cid, be["secret_header"]: secret,
                 "Content-Type": "application/json"})
    return request_json(req, "데이터랩", "hub", group)


def split_pair(text: str, what: str) -> tuple[str, list[str]]:
    sep = ":" if what == "group" else "="
    if sep not in text:
        sys.exit(f"--{what} 형식 오류: '이름{sep}값1,값2' (입력: {text!r})")
    name, _, vals = text.partition(sep)
    values = [v.strip() for v in vals.split(",") if v.strip()]
    if not name.strip() or not values:
        sys.exit(f"--{what} 형식 오류: 이름과 값이 모두 필요합니다 (입력: {text!r})")
    return name.strip(), values


def common_body(args) -> dict:
    end = dt.date.fromisoformat(args.end) if args.end else dt.date.today()
    start = dt.date.fromisoformat(args.start) if args.start else end - dt.timedelta(days=args.days)
    body = {"startDate": start.isoformat(), "endDate": end.isoformat(), "timeUnit": args.unit}
    if args.device:
        body["device"] = args.device
    if args.gender:
        body["gender"] = args.gender
    if args.ages:
        body["ages"] = [a.strip() for a in args.ages.split(",") if a.strip()]
    return body


def build_trend(args) -> tuple[str, dict]:
    groups = [{"groupName": q, "keywords": [q]} for q in args.queries]
    for g in args.group:
        name, kws = split_pair(g, "group")
        groups.append({"groupName": name, "keywords": kws})
    if not 1 <= len(groups) <= 5:
        sys.exit("검색어/그룹은 1~5개여야 합니다")
    body = common_body(args)
    body["keywordGroups"] = groups
    return TREND_PATH, body


def build_shopping(args) -> tuple[str, dict]:
    mode = args.mode
    body = common_body(args)
    if mode in DROP:  # 결과 축과 겹치는 필터는 제외
        body.pop(DROP[mode], None)
    if mode == "categories":
        if not 1 <= len(args.category) <= 3:
            sys.exit("--category 'name=코드1,코드2' 를 1~3개 지정하세요")
        body["category"] = [{"name": n, "param": p}
                            for n, p in (split_pair(c, "category") for c in args.category)]
    else:
        if len(args.category) != 1:
            sys.exit("--category 쇼핑 분야 코드를 하나 지정하세요 (예: 50000000)")
        body["category"] = args.category[0]
        if mode == "keywords":
            if not 1 <= len(args.keyword) <= 5:
                sys.exit("--keyword '그룹이름=검색어' 를 1~5개 지정하세요 (검색어는 그룹당 1개)")
            body["keyword"] = [{"name": n, "param": p}
                               for n, p in (split_pair(k, "keyword") for k in args.keyword)]
        elif mode.startswith("keyword-"):
            if len(args.keyword) != 1:
                sys.exit("--keyword 검색어를 하나 지정하세요")
            body["keyword"] = args.keyword[0]
    return SHOPPING_PATHS[mode], body


def print_table(data: dict) -> None:
    print(f"{data.get('startDate')} ~ {data.get('endDate')} ({data.get('timeUnit')}) / ratio: 구간 내 최대=100")
    for r in data.get("results", []):
        print(f"\n■ {r.get('title')}")
        for row in r.get("data", []):
            group = f"  [{row['group']}]" if "group" in row else ""
            print(f"  {row.get('period')}{group}  {row.get('ratio')}")


def main() -> None:
    ap = argparse.ArgumentParser(description="네이버 데이터랩 (검색어 트렌드 / 쇼핑인사이트)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_common(p):
        p.add_argument("--start", help="시작일 YYYY-MM-DD (생략하면 종료일 기준 --days 일 전)")
        p.add_argument("--end", help="종료일 YYYY-MM-DD (기본 오늘)")
        p.add_argument("--days", type=int, default=90, help="--start 생략 시 조회 일수 (기본 90)")
        p.add_argument("--unit", choices=["date", "week", "month"], default="date",
                       help="구간 단위 (기본 date)")
        p.add_argument("--device", choices=["pc", "mo"], help="기기 필터 (기본 전체)")
        p.add_argument("--gender", choices=["m", "f"], help="성별 필터 (기본 전체)")
        p.add_argument("--ages", help="연령 코드 쉼표 구분 (트렌드: 1~11, 쇼핑: 10,20,...,60)")
        p.add_argument("--format", choices=["text", "json"], default="text", help="출력 형식")
        p.add_argument("--out", help="원본 JSON 저장 경로")
        p.add_argument("--no-usage", action="store_true", help="끝에 사용량 요약을 출력하지 않음")

    t = sub.add_parser("trend", help="검색어 트렌드")
    t.add_argument("queries", nargs="*", help="비교할 검색어 (각각 하나의 그룹)")
    t.add_argument("--group", action="append", default=[], help="'그룹명:검색어1,검색어2' (반복 가능, 총 5그룹까지)")
    add_common(t)

    s = sub.add_parser("shopping", help="쇼핑인사이트")
    s.add_argument("--mode", choices=list(SHOPPING_PATHS), default="categories",
                   help="categories=분야별, device/gender/age=분야의 기기/성별/연령별, "
                        "keywords=키워드별, keyword-*=키워드의 기기/성별/연령별")
    s.add_argument("--category", action="append", default=[],
                   help="categories: '이름=코드1,코드2'(최대 3), 그 외: 분야 코드 하나")
    s.add_argument("--keyword", action="append", default=[],
                   help="keywords: '그룹이름=검색어'(최대 5), keyword-*: 검색어 하나")
    add_common(s)

    args = ap.parse_args()
    path, body = build_trend(args) if args.cmd == "trend" else build_shopping(args)
    cid, secret = load_credentials()
    group = "trend" if args.cmd == "trend" else "shopping"
    data = post(path, body, cid, secret, group)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"저장: {out}")
    elif args.format == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print_table(data)

    if not args.no_usage:  # 표준 출력(JSON 등)을 깨지 않도록 stderr로 출력
        usage.print_summary([group])


if __name__ == "__main__":
    main()
