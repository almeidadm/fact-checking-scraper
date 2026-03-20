from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List

from scrapy.crawler import CrawlerProcess
from scrapy.settings import Settings
from scrapy.spiderloader import SpiderLoader

from .logging import configure_logging, get_logger
from .utils import utc_now_iso

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def build_settings(
    data_dir: Path,
    run_id: str,
    *,
    ignore_existing_seen_state: bool = False,
) -> Settings:
    settings = Settings()
    settings.set("SPIDER_MODULES", ["factcheck_scrape.spiders"])
    settings.set("NEWSPIDER_MODULE", "factcheck_scrape.spiders")
    settings.set("ITEM_PIPELINES", {"factcheck_scrape.pipelines.FactCheckPipeline": 300})
    settings.set(
        "DOWNLOADER_MIDDLEWARES",
        {"factcheck_scrape.middlewares.ScraplingFallbackMiddleware": 750},
    )
    settings.set("ROBOTSTXT_OBEY", False)
    settings.set("LOG_ENABLED", True)
    settings.set("LOG_STDOUT", False)
    settings.set("LOG_LEVEL", "INFO")
    settings.set("USER_AGENT", DEFAULT_USER_AGENT)
    settings.set(
        "DEFAULT_REQUEST_HEADERS",
        {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    settings.set("HTTPERROR_ALLOWED_CODES", [403, 404])
    settings.set("FACTCHECK_SCRAPLING_HEADLESS", True)
    settings.set("FACTCHECK_SCRAPLING_SOLVE_CLOUDFLARE", True)
    settings.set("FACTCHECK_SCRAPLING_TIMEOUT_MS", 60000)
    settings.set("FACTCHECK_SCRAPLING_WAIT_MS", 1000)
    settings.set("FACTCHECK_SCRAPLING_BLOCK_STATUSES", [403, 429, 503])
    settings.set("FACTCHECK_SCRAPLING_REAL_CHROME", False)
    settings.set("FACTCHECK_SCRAPLING_BLOCK_WEBRTC", False)
    settings.set("FACTCHECK_SCRAPLING_HIDE_CANVAS", False)
    settings.set("FACTCHECK_SCRAPLING_ALLOW_WEBGL", True)
    settings.set("FACTCHECK_IGNORE_EXISTING_SEEN_STATE", ignore_existing_seen_state)
    settings.set("FACTCHECK_DATA_DIR", str(data_dir))
    settings.set("FACTCHECK_RUN_ID", run_id)
    return settings


def list_spiders() -> List[str]:
    settings = build_settings(Path("data"), "dry")
    loader = SpiderLoader(settings)
    return sorted(loader.list())


def run_spider(
    spider_name: str,
    data_dir: Path,
    run_id: str,
    *,
    ignore_existing_seen_state: bool = False,
) -> None:
    available = list_spiders()
    if spider_name not in available:
        raise ValueError(f"Unknown spider: {spider_name}. Available: {', '.join(available)}")
    settings = build_settings(
        data_dir,
        run_id,
        ignore_existing_seen_state=ignore_existing_seen_state,
    )
    log_dir = Path("logs")
    configure_logging(run_id, log_dir)
    logger = get_logger("runner")
    logger.info("spider_run_start", spider=spider_name, run_id=run_id, started_at=utc_now_iso())

    process = CrawlerProcess(settings)
    process.crawl(spider_name)
    process.start()

    logger.info("spider_run_end", spider=spider_name, run_id=run_id, finished_at=utc_now_iso())


def run_all_spiders(
    data_dir: Path,
    run_id: str,
    *,
    ignore_existing_seen_state: bool = False,
) -> None:
    configure_logging(run_id, Path("logs"))
    logger = get_logger("runner")
    names = list_spiders()
    logger.info("run_all_start", spiders=names, run_id=run_id)
    for name in names:
        command = [
            sys.executable,
            "-m",
            "factcheck_scrape.cli",
            "run",
            "--spider",
            name,
            "--data-dir",
            str(data_dir),
            "--run-id",
            run_id,
        ]
        if ignore_existing_seen_state:
            command.append("--ignore-existing-seen-state")
        logger.info("run_all_spawn", spider=name, cmd=" ".join(command))
        subprocess.run(command, check=False)
    logger.info("run_all_end", spiders=names, run_id=run_id)
