"""zipdao-crawl — 로컬 크롤링 CLI.

    zipdao-crawl list                     등록된 소스 목록
    zipdao-crawl run <source> [옵션]      한 소스 수집
    zipdao-crawl run all [옵션]           구현된 모든 소스 수집

옵션: --since 2021 --until 2026 --limit N --force --data-dir PATH
"""

from __future__ import annotations

import argparse
import logging
import sys

from zipdao_core.config import load_settings
from zipdao_core.http import HttpClient
from zipdao_core.storage import Storage
from zipdao_crawlers.base import CrawlEngine, CrawlStats
from zipdao_crawlers.registry import SourceInfo, get_source, iter_sources


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )


def _cmd_list(_args: argparse.Namespace) -> int:
    by_cat: dict[str, list[SourceInfo]] = {}
    for s in iter_sources():
        by_cat.setdefault(s.category, []).append(s)
    for category, sources in by_cat.items():
        print(f"\n■ {category}")
        for s in sources:
            mark = "✅" if s.implemented else "⬜"
            print(f"  {mark} {s.key:<14} {s.name:<20} {s.base_url}")
            if s.notes:
                print(f"       └ {s.notes}")
    print(
        "\n✅=구현됨, ⬜=미구현(사이트 실측 후 sources/ 에 추가 필요)\n"
    )
    return 0


def _run_source(info: SourceInfo, args: argparse.Namespace) -> CrawlStats | None:
    if info.crawler is None:
        logging.warning("소스 '%s'(%s)는 아직 미구현 — 건너뜀.", info.key, info.name)
        return None
    settings = load_settings()
    data_dir = args.data_dir or settings.data_dir
    storage = Storage(data_dir / "raw")
    with HttpClient(
        user_agent=settings.user_agent,
        timeout=settings.request_timeout,
        rate_limit_per_sec=settings.rate_limit_per_sec,
    ) as http:
        crawler = info.crawler(http)
        crawler.key = info.key
        crawler.name = info.name
        crawler.base_url = info.base_url
        engine = CrawlEngine(crawler, storage)
        logging.info("수집 시작: %s (%s) → %s", info.key, info.name, storage.raw_dir)
        stats = engine.run(
            since=args.since, until=args.until, limit=args.limit, force=args.force
        )
    logging.info(
        "완료: %s — 신규 %d, 스킵 %d, 첨부 %d, 실패 %d, 오류 %d",
        stats.source, stats.notices_new, stats.notices_skipped,
        stats.assets_downloaded, stats.assets_failed, len(stats.errors),
    )
    return stats


def _cmd_run(args: argparse.Namespace) -> int:
    if args.source == "all":
        targets = [s for s in iter_sources() if s.implemented]
        if not targets:
            print(
                "구현된 소스가 아직 없습니다. `zipdao-crawl list`로 상태를 확인하세요.",
                file=sys.stderr,
            )
            return 1
    else:
        try:
            targets = [get_source(args.source)]
        except KeyError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    for info in targets:
        _run_source(info, args)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zipdao-crawl", description="공공임대 공고 로컬 크롤러")
    parser.add_argument("-v", "--verbose", action="store_true", help="DEBUG 로그")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="등록된 소스 목록")

    run = sub.add_parser("run", help="소스 수집")
    run.add_argument("source", help="소스 key 또는 'all'")
    run.add_argument("--since", type=int, default=None, help="시작 연도(포함)")
    run.add_argument("--until", type=int, default=None, help="종료 연도(포함)")
    run.add_argument("--limit", type=int, default=None, help="신규 공고 최대 건수")
    run.add_argument("--force", action="store_true", help="이미 수집된 공고도 재수집")
    run.add_argument("--data-dir", type=_path, default=None, help="데이터 루트(기본 ./data)")
    return parser


def _path(value: str):
    from pathlib import Path

    return Path(value).expanduser().resolve()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(getattr(args, "verbose", False))
    if args.command == "list":
        return _cmd_list(args)
    if args.command == "run":
        return _cmd_run(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
