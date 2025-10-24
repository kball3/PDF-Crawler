from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup
from tqdm import tqdm

from .config import CrawlConfig
from .fetchers import FetchResult, PlaywrightFetcher, StaticFetcher, playwright_fetcher
from .models import PDFDocument
from .storage import PDFStorage
from .utils import configure_logging

LOGGER = logging.getLogger("pdf_crawler.crawler")


@dataclass
class PageTask:
    url: str
    depth: int


class CrawlSession:
    def __init__(
        self,
        config: CrawlConfig,
        static_fetcher: StaticFetcher,
        playwright_fetcher: Optional[PlaywrightFetcher],
    ) -> None:
        self.config = config
        self.static_fetcher = static_fetcher
        self.playwright_fetcher = playwright_fetcher
        self.storage = PDFStorage(config.output_dir)
        self.visited: Set[str] = set()
        self.downloaded: Dict[str, PDFDocument] = {}
        self.allowed_domains = {urlparse(config.url).netloc}
        self.robots_cache: Dict[str, Optional[object]] = {}

    async def run(self) -> List[PDFDocument]:
        queue: Deque[PageTask] = deque([PageTask(self.config.url, 0)])
        progress = tqdm(total=0, unit="page", desc="Crawling", leave=False)
        try:
            sem = asyncio.Semaphore(self.config.concurrency)
            tasks: Set[asyncio.Task[None]] = set()

            async def schedule(task: PageTask) -> None:
                async with sem:
                    await self._process(task, queue)

            while queue or tasks:
                while queue and len(tasks) < self.config.concurrency:
                    task = queue.popleft()
                    if task.url in self.visited:
                        continue
                    self.visited.add(task.url)
                    coro = schedule(task)
                    tasks.add(asyncio.create_task(coro))
                    progress.total += 1
                    progress.refresh()
                if tasks:
                    done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    for _ in done:
                        progress.update(1)
                else:
                    await asyncio.sleep(0.1)
        finally:
            progress.close()
        return list(self.downloaded.values())

    async def _process(self, task: PageTask, queue: Deque[PageTask]) -> None:
        if not self._is_allowed(task.url):
            LOGGER.debug("Skipping disallowed url %s", task.url)
            return
        result = await self._fetch_page(task.url)
        if not result:
            return
        pdfs = self._extract_pdfs(result)
        for pdf_url, context in pdfs:
            if pdf_url not in self.downloaded:
                try:
                    document = self.storage.build_document(
                        url=pdf_url,
                        source_page=result.final_url,
                        context=context,
                    )
                    self.downloaded[pdf_url] = document
                    LOGGER.info("Downloaded %s -> %s", pdf_url, document.filename)
                except Exception as exc:
                    LOGGER.warning("Failed to download PDF %s: %s", pdf_url, exc)
        if task.depth < self.config.max_depth:
            for link in self._extract_links(result):
                if link not in self.visited:
                    queue.append(PageTask(link, task.depth + 1))

    async def _fetch_page(self, url: str) -> Optional[FetchResult]:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, self.static_fetcher.fetch, url)
        if result and not self._requires_playwright(result):
            return result
        if self.playwright_fetcher:
            LOGGER.debug("Falling back to Playwright for %s", url)
            dynamic_result = await self.playwright_fetcher.fetch(url)
            if dynamic_result:
                return dynamic_result
        return result

    def _requires_playwright(self, result: FetchResult) -> bool:
        if result.detected_pdfs:
            return False
        soup = BeautifulSoup(result.content, "html.parser")
        if soup.find_all(lambda tag: tag.name in {"a", "iframe", "embed"} and tag.get("href") or tag.get("src")):
            return False
        script_tags = soup.find_all("script")
        if len(script_tags) > 10 and len(soup.get_text(strip=True)) < 200:
            return True
        if soup.find(attrs={"data-reactroot": True}) or soup.find(attrs={"data-reactid": True}):
            return True
        if soup.find(attrs={"ng-app": True}) or soup.find(id="app"):
            return True
        return False

    def _extract_links(self, result: FetchResult) -> Iterable[str]:
        soup = BeautifulSoup(result.content, "html.parser")
        base_url = result.final_url
        seen: Set[str] = set()
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            if href.startswith("mailto:") or href.startswith("javascript:"):
                continue
            absolute = self._normalize(urljoin(base_url, href))
            if self._is_same_domain(absolute) and absolute not in seen:
                seen.add(absolute)
                yield absolute

    def _extract_pdfs(self, result: FetchResult) -> List[Tuple[str, Optional[str]]]:
        pdfs: Dict[str, Optional[str]] = {}
        if result.detected_pdfs:
            for url in result.detected_pdfs.values():
                pdfs[url] = "Detected via network request"
        soup = BeautifulSoup(result.content, "html.parser")
        base_url = result.final_url
        for tag in soup.find_all(["a", "iframe", "embed", "object" ]):
            url_attr = tag.get("href") or tag.get("src") or tag.get("data")
            if not url_attr:
                continue
            absolute = self._normalize(urljoin(base_url, url_attr))
            if not absolute.lower().endswith(".pdf") and tag.get("type") != "application/pdf":
                continue
            context = self._describe_context(tag)
            pdfs.setdefault(absolute, context)
        return list(pdfs.items())

    def _describe_context(self, tag) -> Optional[str]:
        text = tag.get_text(" ", strip=True)
        if text:
            return text
        parent = tag.find_parent()
        if parent:
            return parent.get_text(" ", strip=True)[:200]
        return None

    def _normalize(self, url: str) -> str:
        clean, _ = urldefrag(url)
        return clean

    def _is_same_domain(self, url: str) -> bool:
        netloc = urlparse(url).netloc
        return netloc in self.allowed_domains

    def _is_allowed(self, url: str) -> bool:
        if not self.config.respect_robots_txt:
            return True
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        robot = self.robots_cache.get(base)
        if robot is None:
            from urllib import robotparser

            rp = robotparser.RobotFileParser()
            rp.set_url(urljoin(base, "/robots.txt"))
            try:
                rp.read()
            except Exception as exc:  # pragma: no cover
                LOGGER.debug("Failed to read robots.txt for %s: %s", base, exc)
                self.robots_cache[base] = None
                return True
            self.robots_cache[base] = rp
            robot = rp
        if robot is None:
            return True
        return robot.can_fetch("UniversalPDFCrawler", url)


async def crawl_async(config: CrawlConfig, verbose: bool = False) -> List[PDFDocument]:
    configure_logging(verbose)
    static = StaticFetcher(timeout=config.timeout, retries=config.retries)
    async with playwright_fetcher(timeout=config.timeout, auth=config.auth) as playwright:
        session = CrawlSession(config, static, playwright)
        return await session.run()


def crawl(config: CrawlConfig, verbose: bool = False) -> List[PDFDocument]:
    return asyncio.run(crawl_async(config, verbose=verbose))
