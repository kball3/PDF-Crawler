from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Dict, Optional

import requests
from playwright.async_api import BrowserContext, Playwright, async_playwright

from .config import AuthConfig

LOGGER = logging.getLogger("pdf_crawler.fetchers")


@dataclass
class FetchResult:
    url: str
    content: str
    final_url: str
    from_playwright: bool = False
    detected_pdfs: Dict[str, str] | None = None
    content_type: str | None = None


class StaticFetcher:
    def __init__(self, timeout: int = 30, retries: int = 2, session: Optional[requests.Session] = None):
        self.timeout = timeout
        self.retries = retries
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", "UniversalPDFCrawler/0.1")

    def fetch(self, url: str) -> Optional[FetchResult]:
        for attempt in range(self.retries + 1):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                if "application/pdf" in content_type:
                    return FetchResult(
                        url=url,
                        content="",
                        final_url=response.url,
                        detected_pdfs={response.url: response.url},
                        content_type=content_type,
                    )
                return FetchResult(
                    url=url,
                    content=response.text,
                    final_url=response.url,
                    content_type=content_type,
                )
            except requests.RequestException as exc:
                LOGGER.warning("Static fetch failed for %s (attempt %s/%s): %s", url, attempt + 1, self.retries + 1, exc)
        return None


class PlaywrightFetcher:
    def __init__(self, timeout: int = 30, auth: Optional[AuthConfig] = None):
        self.timeout = timeout
        self.auth = auth
        self._playwright: Optional[Playwright] = None
        self._browser_context: Optional[BrowserContext] = None

    async def __aenter__(self) -> "PlaywrightFetcher":
        self._playwright = await async_playwright().start()
        browser = await self._playwright.chromium.launch(headless=True)
        context_args: Dict[str, object] = {"ignore_https_errors": True}
        self._browser_context = await browser.new_context(**context_args)
        if self.auth:
            await self._perform_login(self.auth)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._browser_context:
            await self._browser_context.close()
        if self._playwright:
            await self._playwright.stop()

    async def _perform_login(self, auth: AuthConfig) -> None:
        assert self._browser_context is not None
        page = await self._browser_context.new_page()
        LOGGER.info("Performing login flow for %s", auth.login_url)
        await page.goto(auth.login_url, wait_until="networkidle", timeout=self.timeout * 1000)
        await page.fill(auth.username_selector, auth.username)
        await page.fill(auth.password_selector, auth.password)
        for field in auth.extra_fields:
            await page.fill(field.selector, field.value)
        await page.click(auth.submit_selector)
        if auth.wait_for_selector:
            await page.wait_for_selector(auth.wait_for_selector, timeout=self.timeout * 1000)
        else:
            await page.wait_for_load_state("networkidle", timeout=self.timeout * 1000)
        await page.close()
        LOGGER.info("Login successful")

    async def fetch(self, url: str) -> Optional[FetchResult]:
        if not self._browser_context:
            raise RuntimeError("PlaywrightFetcher must be used as an async context manager")
        page = await self._browser_context.new_page()
        pdf_urls: Dict[str, str] = {}

        def handle_response(response):
            ct = response.headers.get("content-type", "").lower()
            if "application/pdf" in ct:
                pdf_urls[response.url] = response.url

        page.on("response", handle_response)
        try:
            await page.goto(url, wait_until="networkidle", timeout=self.timeout * 1000)
            content = await page.content()
            for item in pdf_urls:
                LOGGER.debug("Detected PDF via network: %s", item)
            return FetchResult(
                url=url,
                content=content,
                final_url=page.url,
                from_playwright=True,
                detected_pdfs=pdf_urls or None,
                content_type="text/html",
            )
        except Exception as exc:
            LOGGER.warning("Playwright fetch failed for %s: %s", url, exc)
            return None
        finally:
            await page.close()


@asynccontextmanager
async def playwright_fetcher(timeout: int = 30, auth: Optional[AuthConfig] = None) -> AsyncIterator[PlaywrightFetcher]:
    fetcher = PlaywrightFetcher(timeout=timeout, auth=auth)
    await fetcher.__aenter__()
    try:
        yield fetcher
    finally:
        await fetcher.__aexit__(None, None, None)
