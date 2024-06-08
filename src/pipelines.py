import shutil
from pathlib import Path
from urllib.parse import urlparse

import scrapy
from scrapy.pipelines.files import FilesPipeline
from scrapy.utils.project import get_project_settings

from src.items import LegalEntityItem
from src.spiders import LegalEntitySpider

SETTINGS = get_project_settings()


class LegalEntityPipeline(FilesPipeline):
    def file_path(self, request, response=None, info=None, *, item=None):
        """
        returns the relative save location for the to-download file

        Final file location will be FILES_STORE / path
        with FILES_STORE coming from the scrapy settings
        """
        # request.url ~= https://www.ejustice.just.fgov.be/tsv_pdf/2020/03/16/20039943.pdf
        path = urlparse(request.url).path
        return path

    def item_completed(self, results, item, info): ...

    def process_item(self, item: scrapy.Item, spider: scrapy.Spider):
        if isinstance(item, LegalEntityItem) and isinstance(spider, LegalEntitySpider):
            return super().process_item(item, spider)

        return item

    def close_spider(self, spider: scrapy.Spider):
        """
        cleans up the temporary PDF files at the end of the run

        if SETTINGS
        """
        if isinstance(spider, LegalEntitySpider) and SETTINGS["CLEANUP_FILES_STORE"]:
            spider.logger.info(f"Cleaning up {SETTINGS['FILES_STORE']}")
            folder = Path(SETTINGS["FILES_STORE"])
            if folder.exists():
                shutil.rmtree(str(folder))
