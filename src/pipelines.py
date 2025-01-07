import json
import logging
import shutil
import time
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

import scrapy
from scrapy.exceptions import DropItem
from scrapy.pipelines.files import FilesPipeline
from scrapy.utils.project import get_project_settings

from src.extract_text import extract_text
from src.items import LegalEntityItem
from src.spiders import BaseLegalEntitySpider

SETTINGS = get_project_settings()

# Azure info is used a lot (per putting a BLOB once)
azurelogger = logging.getLogger("azure")
azurelogger.setLevel(logging.WARNING)


class LegalEntityFilePipeline(FilesPipeline):
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

        saves the publication as a JSON file in Azure storage
        (either PDF was digital from start or we OCR'ed it using Azure Cognitive Services)
        """
        status, result = results[0]  # only one pdf is downloaded per item so results is always of length 1

        if not status and SETTINGS["ROBOTSTXT_OBEY"]:
            raise DropItem(f"{item['file_urls'][0]} could not be downloaded due to `ROBOTSTXT_OBEY=True`.")

        if not status:
            raise DropItem(f"Something went wrong when downloading {item['file_urls'][0]}.")

        publication_date = item["publication_date"]
        if not publication_date:
            raise DropItem(f"Publication date was not correctly extracted for {item['file_urls'][0]}.")

        item["file_path"] = str(Path(SETTINGS["FILES_STORE"]) / Path(result["path"]).relative_to("/"))

        return item

    def process_item(self, item: scrapy.Item, spider: scrapy.Spider):
        """
        Only runs this pipeline for LegalEntityItems and if the Spider was LegalEntitySpider
        """
        if isinstance(item, LegalEntityItem) and isinstance(spider, BaseLegalEntitySpider):
            return super().process_item(item, spider)

        return item

    def close_spider(self, spider: scrapy.Spider):
        """
        cleans up the temporary PDF files at the end of the run

        this is only done if CLEANUP is set in the project settings
        """
        if isinstance(spider, BaseLegalEntitySpider) and spider.settings["CLEANUP_FILESTORE"]:
            spider.logger.info(f"Cleaning up {spider.settings['FILES_STORE']}")
            folder = Path(SETTINGS["FILES_STORE"])
            if folder.exists():
                shutil.rmtree(str(folder))


class LegalEntityPipeline:
    async def process_item(self, item, spider):
        """Runs after the PDF was downloaded. Runs the Azure OCR as a coroutine to not block
        the scrapy processes.

        saves the publication as a JSON file in Azure storage
        (either PDF was digital from start or we OCR'ed it using Azure Cognitive Services)
        """
        if not isinstance(item, LegalEntityItem) or not isinstance(spider, BaseLegalEntitySpider):
            return item

        vat = item["vat"]
        publication_date = item["publication_date"]
        publication_number = item["publication_number"]

        if not vat or not publication_date or not publication_number:
            raise DropItem(
                f"vat: '{vat}' - publication date: '{publication_date}' - publication number '{publication_number}'"
                "was not retrieved correctly (i.e. null)."
            )

        publication = item["publication_meta"]
        pdf_path = item["file_path"]

        start = time.perf_counter()
        text, is_digital = await extract_text(
            pdf_path,
            do_ocr=spider.settings["OCR"],
            endpoint=spider.document_intelligence_url,
            credential=spider.azure_credential,
        )

        if not is_digital and not spider.settings["OCR"]:
            raise DropItem(f"{item['file_urls'][0]} is a scan and `OCR=False`.")

        duration = timedelta(seconds=time.perf_counter() - start)
        spider.logger.debug(f"Extracted text in {duration} from {'digital' if is_digital else 'scan'} PDF.")

        publication["text"] = text
        publication["is_digital"] = is_digital
        meta_path = str(
            Path(item["vat"])
            / str(publication_date.year)
            / str(publication_date.month)
            / str(publication_date.day)
            / f"{item['publication_number']}.json"
        )
        blob_client = spider.blob_service_client.get_blob_client(container=spider.azure_container_name, blob=meta_path)
        blob_client.upload_blob(json.dumps(publication).encode("utf-8"), overwrite=True)
        return item

    def close_spider(self, spider: scrapy.Spider):
        """
        cleans up the temporary PDF files at the end of the run

        CLEANUP_FILESTORE deletes tmp_pdfs ==> forces redownload of a pdf when not available on BLOB
        CLEANUP_BLOBSTORE deletes Azure Container content ==> forces Scrapy Item in next run
        """
        if isinstance(spider, BaseLegalEntitySpider) and spider.settings["CLEANUP_BLOBSTORE"]:
            container = spider.azure_container_name
            spider.logger.info(f"Cleaning up BLOBs on {container}")
            blobs = spider.container_client.list_blob_names()
            for blob in blobs:
                blob_client = spider.blob_service_client.get_blob_client(container=container, blob=blob)
                blob_client.delete_blob("include")
