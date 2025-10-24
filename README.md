# Universal Enterprise PDF Crawler

The Universal Enterprise PDF Crawler is a hybrid static and dynamic web crawler that discovers and downloads PDF documents from modern web applications. It automatically switches between fast HTTP requests for static pages and Playwright-powered browser automation for JavaScript heavy experiences. The crawler extracts PDFs from links, embeds, network activity, and provides detailed metadata for every document.

## Features

- **Automatic rendering detection** – Inspects responses to determine when a page requires JavaScript execution, seamlessly falling back to Playwright when needed.
- **Hybrid crawling engine** – Combines `requests` for static pages with Playwright for SPAs to balance completeness and performance.
- **Multi-source PDF discovery** – Captures PDFs exposed via links, iframes, embeds, `<object>` tags, and Playwright network activity.
- **Enhanced metadata** – Stores file size, inferred titles, download location, source URL, and contextual text surrounding each PDF.
- **Authentication support** – Optional JSON-based configuration to automate login flows (form filling, extra fields, wait conditions).
- **Robust operations** – Retries, concurrent page crawling, robots.txt awareness, checkpointed downloads, and rich logging with progress reporting.
- **Organized storage** – PDFs are grouped by domain with collision-safe, human-friendly file names that incorporate PDF metadata when available.

## Requirements

- Python 3.10+
- Playwright Chromium browser (install with `playwright install chromium`)

Install the project dependencies:

```bash
pip install -e .
playwright install chromium
```

Environment variables can be placed in a `.env` file and are automatically loaded when running the CLI (e.g., `PDF_CRAWLER_OUTPUT`, `PDF_CRAWLER_DEPTH`).

## Quick start

Run the crawler against a target URL:

```bash
pdf-crawler https://example.com --output downloads/example
```

The command above downloads PDFs into the `downloads/example` directory and prints structured JSON metadata for each document to standard output.

### Selecting depth and concurrency

```bash
pdf-crawler https://example.com --max-depth 2 --concurrency 5
```

### Respecting robots.txt

Robots.txt is respected by default. To ignore it:

```bash
pdf-crawler https://example.com --ignore-robots
```

### Authentication

Provide an authentication JSON file with login details:

```json
{
  "login_url": "https://example.com/login",
  "username": "alice@example.com",
  "password": "super-secret",
  "username_selector": "input#email",
  "password_selector": "input#password",
  "submit_selector": "button[type=submit]",
  "wait_for_selector": "nav .profile"
}
```

Run the crawler with authentication:

```bash
pdf-crawler https://example.com/portal --auth-config auth.json
```

### Full configuration file

Instead of CLI flags you can supply a configuration JSON file:

```json
{
  "url": "https://example.com",
  "output_dir": "downloads/example",
  "max_depth": 2,
  "concurrency": 4,
  "timeout": 45,
  "respect_robots_txt": true,
  "retries": 3
}
```

Execute with:

```bash
pdf-crawler --config crawl.json
```

CLI flags override values loaded from the configuration file, and the `--auth-config` file can be combined with `--config` if needed.

## Output

Each downloaded PDF is reported to stdout as JSON with fields:

- `source_page` – The page URL where the PDF was discovered.
- `pdf_url` – The resolved URL used to download the PDF.
- `saved_as` – Local filesystem path of the downloaded PDF.
- `title` – Title extracted from the PDF metadata (when available).
- `context` – Snippet of text near the link/embed used to locate the PDF.
- `size_bytes` – File size on disk.

## Development notes

- Logging is INFO level by default; add `--verbose` for detailed Playwright and network diagnostics.
- The crawler stores robots.txt parsers per-domain to minimize requests.
- Metadata extraction uses `pypdf`; this is best effort and failures are logged at debug level.

## Troubleshooting

- Ensure Chromium is installed for Playwright (`playwright install chromium`).
- When crawling behind authentication, validate CSS selectors and optional wait conditions in your JSON file.
- For self-signed certificates, Playwright is configured to ignore HTTPS errors.

## License

MIT
