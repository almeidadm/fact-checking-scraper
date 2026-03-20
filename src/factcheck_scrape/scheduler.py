from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import yaml
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .logging import configure_logging, get_logger


def load_schedule(config_path: Path) -> Dict[str, Any]:
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not payload:
        return {"timezone": "UTC", "jobs": []}
    payload.setdefault("timezone", "UTC")
    payload.setdefault("jobs", [])
    return payload


def schedule_jobs(config_path: Path, data_dir: Path) -> BlockingScheduler:
    config = load_schedule(config_path)
    scheduler = BlockingScheduler(timezone=config.get("timezone", "UTC"))
    logger = get_logger("scheduler")

    for job in config.get("jobs", []):
        if not job.get("enabled", True):
            continue
        name = job.get("name") or job.get("spider")
        spider = job.get("spider")
        cron = job.get("cron")
        if not spider or not cron:
            logger.warning("job_invalid", job=job)
            continue
        trigger = CronTrigger.from_crontab(cron)
        scheduler.add_job(
            run_spider_job,
            trigger=trigger,
            args=[spider, data_dir],
            id=name,
            name=name,
            replace_existing=True,
        )
        logger.info("job_scheduled", spider=spider, cron=cron, name=name)
    return scheduler


def run_spider_job(spider: str, data_dir: Path) -> None:
    command = [
        sys.executable,
        "-m",
        "factcheck_scrape.cli",
        "run",
        "--spider",
        spider,
        "--data-dir",
        str(data_dir),
    ]
    logger = get_logger("scheduler")
    logger.info("job_start", spider=spider, cmd=" ".join(command))
    subprocess.run(command, check=False)
    logger.info("job_end", spider=spider)


def run_schedule(config_path: Path, data_dir: Path) -> None:
    configure_logging("scheduler", Path("logs"))
    scheduler = schedule_jobs(config_path, data_dir)
    scheduler.start()
