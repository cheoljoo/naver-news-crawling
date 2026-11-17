"""이 도구가 보낸 API 호출 횟수를 로컬에 기록하고 한도 대비 사용량을 보여준다.

왜 직접 세나: NAVER API HUB에는 사용량을 읽는 API도, 사용량 응답 헤더도 없다(콘솔에서만 확인 가능).
한계: **이 PC에서 이 도구가 보낸 성공(HTTP 200) 호출만** 센다. 같은 키를 다른 곳에서 쓰거나 콘솔 기준과
집계 방식이 다르면 어긋난다. 정확한 값은 콘솔(https://console.ncloud.com/naver-api-hub/application) 기준.
날짜 경계는 KST(UTC+9). 문서마다 UTC+9/UTC+0 서술이 달라 콘솔의 기준 시각은 확인하지 못했다.

사용:
    uv run usage.py show                                  # 전체 사용량
    uv run usage.py set search --day 120 --month 3400     # 콘솔 값에 시작값 맞추기
저장 위치: 이 폴더의 .usage.json (gitignore 대상). USAGE_FILE 환경변수로 바꿀 수 있다.
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
FILE = Path(os.environ.get("USAGE_FILE") or Path(__file__).with_name(".usage.json"))

# 콘솔 화면에 표시된 한도 (일 한도 None = 제한 없음). 검색 계열 7종은 한도를 함께 쓴다.
LIMITS = {
    "search": {"label": "검색 API", "day": 25_000, "month": 775_000},
    "trend": {"label": "데이터랩 검색어트렌드", "day": None, "month": 50_000},
    "shopping": {"label": "데이터랩 쇼핑인사이트", "day": None, "month": 50_000},
}
_run: dict[str, int] = {}  # 이번 실행에서 보낸 호출 수


def today() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def _load() -> dict:
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(data: dict) -> None:
    fd, tmp = tempfile.mkstemp(dir=FILE.parent, prefix=".usage.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, FILE)


def record(group: str) -> None:
    """성공 호출 1회를 기록한다. 기록 실패가 본 작업을 막지 않게 오류는 무시한다."""
    _run[group] = _run.get(group, 0) + 1
    try:
        data = _load()
        days = data.setdefault(group, {})
        days[today()] = days.get(today(), 0) + 1
        _save(data)
    except OSError:
        pass


def counts(group: str) -> tuple[int, int]:
    days = _load().get(group, {})
    day = today()
    return days.get(day, 0), sum(v for k, v in days.items() if k.startswith(day[:7]))


def _fmt(used: int, limit) -> str:
    if limit is None:
        return f"{used:>9,}  (한도 없음)"
    return f"{used:>9,} / {limit:,} ({used / limit * 100:.2f}%)"


def lines(groups, show_run: bool = True) -> list[str]:
    out = ["── 사용량 (이 도구가 이 PC에서 보낸 호출 기준, KST) ──"]
    for g in groups:
        lim = LIMITS[g]
        d, m = counts(g)
        run = f"  [이번 실행 {_run.get(g, 0)}회]" if show_run and _run.get(g) else ""
        out.append(f"{lim['label']}{run}")
        out.append(f"  오늘      {_fmt(d, lim['day'])}")
        out.append(f"  이번 달   {_fmt(m, lim['month'])}")
    return out


def print_summary(groups, show_run: bool = True) -> None:
    sys.stdout.flush()  # 결과 출력이 먼저 나온 뒤 요약이 나오도록 순서 보장
    print("\n" + "\n".join(lines(groups, show_run)), file=sys.stderr)
    print("  ※ 콘솔 기준과 다를 수 있음 (make usage 로 자세히)", file=sys.stderr)


def set_baseline(group: str, day: int, month: int) -> None:
    """콘솔에서 읽은 값에 맞춘다. 오늘 값=day, 이번 달 합계=month (month >= day)."""
    if month < day:
        sys.exit("--month 는 --day 이상이어야 합니다 (이번 달 합계에 오늘 값이 포함되므로)")
    data = _load()
    days = data.setdefault(group, {})
    prefix = today()[:7]
    for k in [k for k in days if k.startswith(prefix)]:
        del days[k]
    days[today()] = day
    if month > day:
        days[f"{prefix}-00"] = month - day  # 오늘 이전에 쌓인 분량
    _save(data)


def main() -> None:
    ap = argparse.ArgumentParser(description="API 호출 사용량 (이 도구 기준)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show", help="전체 사용량과 안내 보기")
    s = sub.add_parser("set", help="콘솔에서 읽은 값으로 시작값 맞추기")
    s.add_argument("group", choices=list(LIMITS), help="search | trend | shopping")
    s.add_argument("--day", type=int, required=True, help="콘솔의 당일 사용량")
    s.add_argument("--month", type=int, required=True, help="콘솔의 당월 사용량")
    args = ap.parse_args()

    if args.cmd == "set":
        set_baseline(args.group, args.day, args.month)
        print(f"{LIMITS[args.group]['label']} 시작값 설정: 오늘 {args.day}, 이번 달 {args.month}")
    print("\n".join(lines(LIMITS, show_run=False)))
    if args.cmd == "show":
        print("\n※ 이 도구가 이 PC에서 보낸 성공(HTTP 200) 호출만 센 값입니다. 같은 키를 다른 곳에서 쓰면 반영되지 않으니")
        print("  정확한 값은 콘솔 Application 화면을 확인하고, 어긋나면 `make usage-set`으로 맞추세요.")
        print("※ 한도 안의 호출은 현재 '한시적 무료'로 안내되어 있습니다. 무료 제공량 수치는 문서에 따로 없고,")
        print("  유료 전환 시 별도 공지가 나간다고 합니다. 위 한도는 콘솔에 표시된 호출 상한입니다.")
        print(f"※ 기록 파일: {FILE}")


if __name__ == "__main__":
    main()
