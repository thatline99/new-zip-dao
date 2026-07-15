"""zipdao-crawl 로컬 크롤링 CLI 진입점."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime

from zipdao_core.config import load_settings
from zipdao_core.http import HttpClient
from zipdao_core.storage import Storage
from zipdao_crawlers.base import CrawlEngine, CrawlStats
from zipdao_crawlers.normalize import normalize_for
from zipdao_crawlers.registry import SourceInfo, get_source, iter_sources


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


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
    print("\n✅=구현됨, ⬜=미구현(사이트 실측 후 sources/ 에 추가 필요)\n")
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
        stats = engine.run(since=args.since, until=args.until, limit=args.limit, force=args.force)
    logging.info(
        "완료: %s — 신규 %d, 스킵 %d, 첨부 %d, 실패 %d, 오류 %d",
        stats.source,
        stats.notices_new,
        stats.notices_skipped,
        stats.assets_downloaded,
        stats.assets_failed,
        len(stats.errors),
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


def _cmd_normalize(args: argparse.Namespace) -> int:
    settings = load_settings()
    data_dir = args.data_dir or settings.data_dir
    raw_dir = data_dir / "raw"
    if not raw_dir.exists():
        print(f"데이터 경로 없음: {raw_dir}", file=sys.stderr)
        return 1
    if args.source == "all":
        sources = sorted(p.name for p in raw_dir.iterdir() if p.is_dir())
    else:
        sources = [args.source]

    total = 0
    for src in sources:
        updated = 0
        for manifest in sorted((raw_dir / src).glob("*/*/manifest.json")):
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            raw = data.get("raw") or {}
            normalized = normalize_for(src, raw)
            if not normalized:
                continue
            raw["normalized"] = normalized
            data["raw"] = raw
            manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            updated += 1
        logging.info("정규화: %s — %d건 갱신", src, updated)
        total += updated
    print(f"정규화 완료: 총 {total}건 갱신")
    return 0


def _iter_source_manifests(raw_dir, source: str):
    if source == "all":
        sources = sorted(p.name for p in raw_dir.iterdir() if p.is_dir())
    else:
        sources = [source]
    for src in sources:
        for manifest in sorted((raw_dir / src).glob("*/*/manifest.json")):
            yield src, manifest


def _cmd_parse_docs(args: argparse.Namespace) -> int:
    from zipdao_crawlers.notice_doc import parse_notice_pdf, pick_notice_pdf

    settings = load_settings()
    data_dir = args.data_dir or settings.data_dir
    raw_dir = data_dir / "raw"
    if not raw_dir.exists():
        print(f"데이터 경로 없음: {raw_dir}", file=sys.stderr)
        return 1

    parsed = failed = 0
    with HttpClient(
        user_agent=settings.user_agent,
        timeout=settings.request_timeout,
        rate_limit_per_sec=settings.rate_limit_per_sec,
    ) as http:
        for src, manifest in _iter_source_manifests(raw_dir, args.source):
            if args.limit is not None and parsed >= args.limit:
                break
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            raw = data.get("raw") or {}
            if raw.get("docParse") and not args.force:
                continue
            att = pick_notice_pdf(data.get("attachments") or [])
            if att is None:
                continue
            try:
                resp = http.get(att["url"])
                result = parse_notice_pdf(resp.content)
            except Exception as exc:
                failed += 1
                logging.warning(
                    "공고문 파싱 실패(다음 실행에서 재시도): %s — %s", manifest.parent, exc
                )
                continue
            raw["docParse"] = {
                "parsedAt": datetime.now(UTC).isoformat(timespec="seconds"),
                "file": att.get("filename"),
                **result,
            }
            raw["normalized"] = normalize_for(src, raw)
            data["raw"] = raw
            manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            parsed += 1
            if result:
                logging.info("공고문 파싱: %s — %s", manifest.parent.name, result)
    print(f"공고문 파싱 완료: {parsed}건 갱신, {failed}건 실패")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """CLI 서브커맨드(list/run/normalize) 파서를 만든다."""
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

    norm = sub.add_parser("normalize", help="기존 manifest 에 raw.normalized 백필")
    norm.add_argument("source", help="소스 key 또는 'all'")
    norm.add_argument("--data-dir", type=_path, default=None, help="데이터 루트(기본 ./data)")

    docs = sub.add_parser("parse-docs", help="공고문 PDF 를 받아 나이·가격을 manifest 에 백필")
    docs.add_argument("source", help="소스 key 또는 'all'")
    docs.add_argument("--limit", type=int, default=None, help="이번 실행 최대 처리 건수")
    docs.add_argument("--force", action="store_true", help="이미 파싱한 공고도 다시 파싱")
    docs.add_argument("--data-dir", type=_path, default=None, help="데이터 루트(기본 ./data)")
    return parser


def _path(value: str):
    from pathlib import Path

    return Path(value).expanduser().resolve()


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점 — 인자를 파싱해 서브커맨드를 실행한다."""
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(getattr(args, "verbose", False))
    if args.command == "list":
        return _cmd_list(args)
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "normalize":
        return _cmd_normalize(args)
    if args.command == "parse-docs":
        return _cmd_parse_docs(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
