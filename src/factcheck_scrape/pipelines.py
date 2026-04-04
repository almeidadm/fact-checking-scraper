from __future__ import annotations

from typing import Any, Dict

from scrapy.exceptions import DropItem

from .dedupe import DedupeStore
from .logging import get_logger
from .schema import as_item_dict, normalize_item, validate_item
from .storage import RunCounts, RunWriter
from .utils import canonicalize_url, make_item_id, utc_now_iso


class FactCheckPipeline:
    def __init__(
        self,
        data_dir: str,
        run_id: str,
        *,
        ignore_existing_seen_state: bool = False,
    ) -> None:
        self.data_dir = data_dir
        self.run_id = run_id
        self.ignore_existing_seen_state = ignore_existing_seen_state
        self.crawler = None
        self.dedupe: DedupeStore | None = None
        self.writer: RunWriter | None = None
        self.counts = RunCounts()
        self.spider_started_at = ""
        self.logger = get_logger("pipeline")

    @classmethod
    def from_crawler(cls, crawler):
        data_dir = crawler.settings.get("FACTCHECK_DATA_DIR", "data")
        run_id = crawler.settings.get("FACTCHECK_RUN_ID")
        instance = cls(
            data_dir=data_dir,
            run_id=run_id,
            ignore_existing_seen_state=crawler.settings.getbool(
                "FACTCHECK_IGNORE_EXISTING_SEEN_STATE", False
            ),
        )
        instance.crawler = crawler
        return instance

    def open_spider(self, spider=None):
        spider = self._resolve_spider(spider)
        self.spider_started_at = utc_now_iso()
        agency_id = getattr(spider, "agency_id", spider.name)
        self.dedupe = DedupeStore(
            data_dir=self.data_dir,
            agency_id=agency_id,
            ignore_existing_seen_state=self.ignore_existing_seen_state,
        )
        self.writer = RunWriter(data_dir=self.data_dir, run_id=self.run_id)
        self.logger.info(
            "spider_opened",
            spider=spider.name,
            agency_id=agency_id,
            run_id=self.run_id,
            ignore_existing_seen_state=self.ignore_existing_seen_state,
        )

    def process_item(self, item: Any, spider=None):
        spider = self._resolve_spider(spider)
        self.counts.items_seen += 1
        try:
            payload = self._normalize_item(item, spider)
            validate_item(payload)
        except Exception as exc:
            self.counts.items_invalid += 1
            self.logger.warning(
                "item_invalid",
                spider=spider.name,
                agency_id=getattr(spider, "agency_id", spider.name),
                error=str(exc),
            )
            raise DropItem(str(exc))

        if not self.dedupe or not self.writer:
            raise DropItem("Pipeline not initialized")

        if self.dedupe.is_seen(payload["canonical_url"]):
            self.counts.items_deduped += 1
            raise DropItem("Duplicate item")

        self.dedupe.mark_seen(payload["canonical_url"], payload["source_url"])
        self.writer.write_item(payload)
        self.counts.items_stored += 1
        return payload

    def close_spider(self, spider=None):
        spider = self._resolve_spider(spider)
        if not self.writer:
            return
        finished_at = utc_now_iso()
        agency_id = getattr(spider, "agency_id", spider.name)
        agency_name = getattr(spider, "agency_name", spider.name)
        self.writer.close()
        self.writer.update_run(
            spider_name=spider.name,
            agency_id=agency_id,
            agency_name=agency_name,
            counts=self.counts,
            spider_started_at=self.spider_started_at,
            spider_finished_at=finished_at,
        )
        self.logger.info(
            "spider_closed",
            spider=spider.name,
            agency_id=agency_id,
            run_id=self.run_id,
            **self.counts.to_dict(),
        )

    def _normalize_item(self, item: Any, spider) -> Dict[str, Any]:
        payload = as_item_dict(item)
        payload = normalize_item(payload)

        if not payload.get("spider"):
            payload["spider"] = spider.name
        if not payload.get("agency_id"):
            payload["agency_id"] = getattr(spider, "agency_id", spider.name)
        if not payload.get("agency_name"):
            payload["agency_name"] = getattr(spider, "agency_name", spider.name)
        if not payload.get("run_id"):
            payload["run_id"] = self.run_id
        if not payload.get("collected_at"):
            payload["collected_at"] = utc_now_iso()

        source_url = payload.get("source_url") or payload.get("canonical_url")
        if source_url:
            payload["source_url"] = source_url

        canonical_url = payload.get("canonical_url")
        if not canonical_url and source_url:
            canonicalize_fn = getattr(spider, "canonicalize", canonicalize_url)
            canonical_url = canonicalize_fn(source_url)
            payload["canonical_url"] = canonical_url

        if canonical_url and not payload.get("item_id"):
            payload["item_id"] = make_item_id(payload["agency_id"], canonical_url)

        return payload

    def _resolve_spider(self, spider):
        if spider is not None:
            return spider
        if self.crawler is not None and getattr(self.crawler, "spider", None) is not None:
            return self.crawler.spider
        raise DropItem("Spider instance not available")
