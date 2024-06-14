import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import scrapy
from azure.storage.blob import BlobServiceClient
from scrapy.exceptions import DropItem
from scrapy.pipelines.files import FilesPipeline
from scrapy.utils.project import get_project_settings

from src.items import LegalEntityItem
from src.spiders import LegalEntitySpider

SETTINGS = get_project_settings()
AZURE_STORAGE_ACCOUNT_URL = SETTINGS["AZURE_STORAGE_ACCOUNT_URL"]
AZURE_STORAGE_ACCOUNT_KEY = SETTINGS["AZURE_STORAGE_ACCOUNT_KEY"]
AZURE_CONTAINER_NAME = SETTINGS["AZURE_CONTAINER_NAME"]

# Azure info is used a lot (per putting a BLOB once)
azurelogger = logging.getLogger("azure")
azurelogger.setLevel(logging.WARNING)

blob_service_client = BlobServiceClient(AZURE_STORAGE_ACCOUNT_URL, AZURE_STORAGE_ACCOUNT_KEY)
container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)


class LegalEntityPipeline(FilesPipeline):
    def file_path(self, request, response=None, info=None, *, item=None):
        """
        returns the relative save location for the to-download file

        Final file location will be FILES_STORE / path
        with FILES_STORE coming from the scrapy settings
        """
        # request.url ~= https://www.ejustice.just.fgov.be/tsv_pdf/2020/03/16/20039943.pdf
        path = urlparse(request.url).path.replace("/tsv_pdf", "")
        return path

    def item_completed(self, results, item, info):
        """Runs after the PDF was downloaded.

        saves the metadata of the publication as a JSON file in Azure storage
        saves a digital copy of the pdf in Azure storage
        (either PDF was digital from start or we OCR'ed it using Azure Cognitive Services)

        :param results: _description_
        :param item: _description_
        :param info: _description_
        """
        status, result = results[0]  # only one pdf is downloaded per item so results is always of length 1

        if not status:  # something went wrong when downloading file
            raise DropItem(f"{result['url']} was not successfully retrieved")

        raw_pdf = Path(SETTINGS["FILES_STORE"]) / result["path"]  # noqa
        pub_date = datetime.strptime(item["publication_date"], "%Y-%m-%d").date()
        meta_path = str(
            Path(item["vat"])
            / str(pub_date.year)
            / str(pub_date.month)
            / str(pub_date.day)
            / f"{item['publication_meta']['pubid']}.json"
        )

        blob_client = blob_service_client.get_blob_client(container=AZURE_CONTAINER_NAME, blob=meta_path)
        blob_client.upload_blob(json.dumps(item["publication_meta"]).encode("utf-8"), overwrite=True)
        return item

    def process_item(self, item: scrapy.Item, spider: scrapy.Spider):
        """
        Only runs this pipeline for LegalEntityItems and if the Spider was LegalEntitySpider
        """
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
