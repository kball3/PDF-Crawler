from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from .config import AuthConfig, CrawlConfig
from .crawler import crawl
from .utils import env_default


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Universal Enterprise PDF Crawler")
    parser.add_argument("url", nargs="?", help="Starting URL to crawl")
    parser.add_argument("--output", default=env_default("PDF_CRAWLER_OUTPUT", "downloads"), help="Directory for downloaded PDFs")
    parser.add_argument("--max-depth", type=int, default=int(env_default("PDF_CRAWLER_DEPTH", "1")), help="Maximum crawl depth")
    parser.add_argument("--concurrency", type=int, default=int(env_default("PDF_CRAWLER_CONCURRENCY", "3")), help="Number of concurrent page fetches")
    parser.add_argument("--timeout", type=int, default=int(env_default("PDF_CRAWLER_TIMEOUT", "30")), help="Request timeout in seconds")
    parser.add_argument("--retries", type=int, default=int(env_default("PDF_CRAWLER_RETRIES", "2")), help="Number of retries for failed requests")
    parser.add_argument("--config", type=Path, help="Path to JSON config file")
    parser.add_argument("--auth-config", type=Path, help="Path to JSON file describing authentication flow")
    parser.add_argument("--respect-robots", action="store_true", default=True, help="Respect robots.txt (default: true)")
    parser.add_argument("--ignore-robots", action="store_false", dest="respect_robots", help="Ignore robots.txt directives")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> CrawlConfig:
    if args.config:
        config = CrawlConfig.load(args.config)
        if args.url:
            config.url = args.url
        config.output_dir = Path(args.output)
        config.max_depth = args.max_depth
        config.concurrency = args.concurrency
        config.timeout = args.timeout
        config.retries = args.retries
        config.respect_robots_txt = args.respect_robots
        return config

    if not args.url:
        raise SystemExit("URL is required when no config file is provided")

    auth = None
    if args.auth_config:
        auth_data = json.loads(args.auth_config.read_text())
        auth = AuthConfig.from_dict(auth_data)

    return CrawlConfig(
        url=args.url,
        output_dir=Path(args.output),
        auth=auth,
        max_depth=args.max_depth,
        concurrency=args.concurrency,
        timeout=args.timeout,
        retries=args.retries,
        respect_robots_txt=args.respect_robots,
    )


def main() -> None:
    load_dotenv()
    args = parse_args()
    config = build_config(args)
    documents = crawl(config, verbose=args.verbose)
    for doc in documents:
        print(json.dumps({
            "source_page": doc.source_page,
            "pdf_url": doc.url,
            "saved_as": str(doc.filename),
            "title": doc.title,
            "context": doc.context,
            "size_bytes": doc.size_bytes,
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
