"""
scrapes legal entities from the following web page:
https://www.ejustice.just.fgov.be/cgi_tsv/rech.pl
"""

import logging
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Generator, Iterable, Literal, Optional, Tuple

import scrapy
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
from scrapy.http import Request, Response
from scrapy.selector.unified import SelectorList
from scrapy.utils.project import get_project_settings

from src.items import LegalEntityItem

# Azure info is used a lot (per putting a BLOB once)
azurelogger = logging.getLogger("azure")
azurelogger.setLevel(logging.WARNING)

load_dotenv()
SETTINGS = get_project_settings()

# list of company numbers (VAT number minus BE) to scrape
LEGAL_ENTITIES = [
    {"vat": "0471938850", "start_date": date(year=1998, month=7, day=29), "end_date": date.today()},  # EY consulting
    {"vat": "0463318421", "start_date": None, "end_date": None},  # NORRIQ Belgium
    {"vat": "0799497754", "start_date": None, "end_date": None},  # NORRIQ Financial Services
]


class BaseLegalEntitySpider(scrapy.Spider):
    base_url = "https://www.ejustice.just.fgov.be"
    type: Optional[Literal["vat", "date"]] = None

    def __init__(self, *args, **kwargs):
        # initialize parent class
        super(BaseLegalEntitySpider, self).__init__(*args, **kwargs)

        # get Azure KeyVault secrets
        self.azure_credential = DefaultAzureCredential()
        secret_client = SecretClient(vault_url=os.environ["AZURE_KEYVAULT_URL"], credential=self.azure_credential)
        azure_container_name = secret_client.get_secret("blob-storage-container-name").value
        azure_storage_account_url = secret_client.get_secret("blob-storage-url").value
        self.document_intelligence_url = secret_client.get_secret("document-intelligence-url").value
        ocr_configured_properly = (SETTINGS["OCR"] and self.document_intelligence_url) or not SETTINGS["OCR"]
        if not all((azure_container_name, azure_storage_account_url, ocr_configured_properly)):
            sys.exit(
                "Check if Azure KeyVault secrets are correctly set:\n"
                f"\tblob-storage-container-name: {azure_container_name}\n"
                f"\tblob-storage-url: {azure_storage_account_url}\n"
                f"{'document-intelligence-url: ' + str(self.document_intelligence_url) if SETTINGS['OCR'] else ''}"
            )

        # after type check we know for sure these are set correctly
        self.azure_container_name: str = azure_container_name
        self.azure_storage_account_url: str = azure_storage_account_url

        # initialize Azure Blob storage
        self.blob_service_client = BlobServiceClient(self.azure_storage_account_url, self.azure_credential)
        self.container_client = self.blob_service_client.get_container_client(self.azure_container_name)
        blobs = list(self.container_client.list_blob_names())
        self.vats = {str(Path(blob).parents[-2]) for blob in blobs}
        self.num_pubs = len(blobs)

    def parse(self, response: Response) -> Optional[Iterable[Request] | Generator[scrapy.Item, None, None]]:
        """
        Checks if any publications are found for a given company. If there are more than 100 results, then
        recursively calls itself to get all publication blocks.

        :param response: scrapy.Response
        :yield: a scrapy Request per publication category OR Item
        :return: None when no div elements are found in this act
        """
        meta = response.meta
        any_publications = "Geen tekst komt overeen met uw zoekopdracht" not in response.text

        if not any_publications and "page" not in meta:
            self.logger.info(f"No publications found for {response.url}")
            return None

        # publication element is the `block` per publication
        publication_elements = response.xpath("/html/body/div/div[4]/div/main/div[2]/div/div[*]")

        # process elements on page by collecting publication elements
        if publication_elements:
            meta["publication_elements"] = response.meta.get("publication_elements", []) + publication_elements

        # max number of publication elements on a page = 100, in this case next page needs to be crawled
        if len(publication_elements) == 100:
            meta["page"] = response.meta.get("page", 1) + 1
            url = self.format_url(meta)
            self.logger.debug(f"100 publications on page {response.url}, continueing on next page {meta['page']}")
            yield scrapy.Request(url, callback=self.parse, meta=meta)
        # at least one publication element was found, parse the publications
        elif meta.get("publication_elements"):
            yield from self.parse_publications(meta)
        else:
            self.logger.info(f"No publications found for {response.url}")
            return None

    def parse_publications(self, meta: dict) -> Iterable[scrapy.Item]:
        """Creates a scrapy ItemLoader such that the PDFs get downloaded
        This method gets called multiple times, once per act that contains pdfs

        :param publication_elements: all publication elements found for the legal entity for the given filters
        :param meta: response.meta from previous request
        """
        # scraping based on VAT number, can create a set of already scraped publications for this VAT
        if meta.get("vat"):
            scraped = {Path(item).stem for item in self.container_client.list_blob_names(name_starts_with=meta["vat"])}

        pub_date_threshold = meta["start_date"] or self.settings["PUB_DATE_THRESHOLD"]

        publication_elements: SelectorList = meta["publication_elements"]
        publications = []
        for i, publication_element in enumerate(publication_elements):
            # fetch metadata from the publication element
            urls = publication_element.xpath("./div//a/@href").getall()
            pdf_relative_url, pdf_absolute_url, pubid = self.parse_publication_url(urls)
            company_name = publication_element.xpath("./div/p/font/text()").get()
            company_juridical_form = publication_element.xpath("./div/p/text()[2]").get(default="").strip()
            pub_metadata = [i.strip() for i in publication_element.xpath("./div/a[1]/text()").getall()]

            address, vat, act_description, pub_date_and_number = self.parse_metadata(pub_metadata)
            vat = vat.replace(".", "").strip() if vat else None
            city, zipcode, street = self.extract_address(address)
            publication_date, publication_number = self.extract_publication_date_and_number(pub_date_and_number)

            # Date scrape doesnt have one VAT number, so we check per publication if it's already scraped
            if not meta.get("vat") and vat:
                scraped = {Path(i).stem for i in self.container_client.list_blob_names(name_starts_with=vat)}

            if publication_date and publication_date < pub_date_threshold:
                remaining = len(publication_elements) - (i + 1)
                self.logger.info(f"Threshold date reached {pub_date_threshold}, skipping {remaining} pubs...")
                break

            if not pdf_relative_url:
                url = (
                    self.base_url + f"/cgi_tsv/rech_res.pl?btw={meta.get('vat')}"
                    f"&pdd={publication_date if publication_date else ''}"
                    f"&pdf={publication_date if publication_date else ''}"
                )
                self.logger.debug(f"Could not extract url from publication: {url}")
                continue

            if publication_number in scraped:
                self.logger.info(f"Already scraped {pdf_absolute_url}, skipping download...")
                continue

            publication_meta = {
                "vat": meta.get("vat", vat),
                "pubid": pubid,  # last two digits of publication date year + publication number
                "act_description": act_description,
                "company_name": company_name,
                "company_juridical_form": company_juridical_form,
                "address": address,
                "street": street,
                "zipcode": zipcode,
                "city": city,
                "publication_date": str(publication_date),
                "publication_number": publication_number,
                "publication_link": pdf_absolute_url,
            }
            publications.append(publication_meta)

            self.logger.info(f"Creating Scrapy Item to download {pdf_absolute_url}")
            item = LegalEntityItem(
                vat=meta.get("vat", vat),
                publication_id=pubid,
                publication_number=publication_number,
                publication_date=publication_date,
                publication_meta=publication_meta,
                file_urls=[pdf_absolute_url],
            )
            yield item

    def format_url(self, meta: dict) -> str:
        """creates the to-scrape url based on the meta

        :param meta: _description_
        :return: _description_
        """
        page = meta.get("page")
        if page:
            url = f"{self.base_url}/cgi_tsv/list.pl?language=nl&page={str(page)}"
        else:
            url = f"{self.base_url}/cgi_tsv/rech_res.pl?language=nl"

        if self.type == "vat":
            url += f"&btw={meta['vat']}"

        if self.type == "date":
            url += f"&pdd={meta['start_date'].strftime('%Y-%m-%d')}&pdf={meta['end_date'].strftime('%Y-%m-%d')}"

        return url

    def parse_publication_url(self, urls: list[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """finds the publication url from all the urls in the publication div

        :param urls: list of urls
        :return: pdf_relative_url, pdf_absolute_url, pubid
        """
        urls = [url for url in urls if url.endswith(".pdf")]
        if len(urls) == 1:
            pdf_relative_url = urls[0]
            pdf_absolute_url = self.base_url + pdf_relative_url
            pubid = Path(pdf_relative_url).stem
            return pdf_relative_url, pdf_absolute_url, pubid

        if len(urls) > 1:
            self.logger.error(f"Multiple urls found in the publication div, could not extract pdfurl from {urls}")

        return None, None, None

    def parse_metadata(
        self, pub_metadata: list[str]
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """parses the metadata section in the publication element

        :param pub_metadata: metadata section in publication element
        :return: address, vat, act_description and pub_date_and_number

        example standard format:
        https://www.ejustice.just.fgov.be/cgi_tsv/rech_res.pl?btw=0736812790&pdd=2020-03-16&pdf=2020-03-16

        example no address and act format:
        https://www.ejustice.just.fgov.be/cgi_tsv/rech_res.pl?btw=1009987358&pdd=2024-06-05&pdf=2024-06-05
        (can be outdated - new publications / new companies are sometimes missing it but gets corrected)
        """
        if len(pub_metadata) == 4:
            self.logger.debug("Metadata section of publication is of length 4.")
            address, vat, act_description, pub_date_and_number = pub_metadata
        elif len(pub_metadata) == 6:
            self.logger.debug("Metadata section of publication is of length 6.")
            address, vat, act_description, pub_date_and_number, _, _ = pub_metadata
        else:
            self.logger.warning(f"Unimplemented metadata format with length {len(pub_metadata)}: {pub_metadata}")
            address = vat = act_description = pub_date_and_number = None

        return address, vat, act_description, pub_date_and_number

    def extract_address(self, address: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """extracts the city, zipcode and street from the address metadata section

        :param address: address metadata
        :return: city, zipcode and street

        standard address structure:
        RUE JACQUES JORDAENS 32A, BTE6 1000 BRUXELLES
        """
        if not address:
            self.logger.debug("Address was blank or empty, could not extract city, zipcode, street")
            return None, None, None

        address_matched = re.match(r"^(?P<street>.*)\s(?P<zipcode>\d{4})\s(?P<city>.*)$", address)
        if address_matched:
            street = address_matched.group("street")
            zipcode = address_matched.group("zipcode")
            city = address_matched.group("city")
        else:
            self.logger.warning(f"Could not extract street, zipcode and city from address: '{address}'. ")
            city = street = zipcode = None

        return city, zipcode, street

    def extract_publication_date_and_number(
        self, pub_date_and_number: Optional[str]
    ) -> Tuple[Optional[date], Optional[str]]:
        """extracts the publication date and number

        :param pub_date_and_number: combined date and number
        :return: publication_date, publication_number

        example pub_date_and_number:
        "2024-06-05 / 0402585"
        """
        if not pub_date_and_number:
            self.logger.debug("Could not extract publication date and number from empty pub_date_and_number")
            return None, None

        match = re.match(r"^(?P<date>\d{4}-\d{2}-\d{2})\s/\s(?P<number>\d*-?\d+)$", pub_date_and_number)
        if match:
            self.logger.debug("¨Publication date and number are in standard format")
            publication_date = datetime.strptime(match.group("date"), "%Y-%m-%d").date()
            publication_number = match.group("number")
            return publication_date, publication_number

        # older publications have often only the year specified.
        match = re.match(r"^(?P<date>\d{4})\s/\s(?P<number>\d*-?\d+)$", pub_date_and_number)
        if match:
            self.logger.debug("¨Publication date contains only the year.")
            publication_date = datetime.strptime(match.group("date"), "%Y").date()
            publication_number = match.group("number")
            return publication_date, publication_number

        self.logger.warning(f"Could not extract publication date and number from: '{pub_date_and_number}'")
        publication_date = publication_number = None
        return publication_date, publication_number

    def closed(self, reason: Literal["finished", "cancelled", "cancelled"]) -> None:
        """Called whenever the spider gets closed

        :param reason: reason of the closing of the spider
        """
        if reason != "finished":
            return

        blobs = list(self.container_client.list_blob_names())
        vats = {str(Path(blob).parents[-2]) for blob in blobs}
        num_pubs = len(blobs)
        self.logger.info("Successfully finished scraping run.")
        self.logger.info(f"Created {len(vats - self.vats)} new companies and {num_pubs - self.num_pubs} publications.")
        self.logger.info(f"New companies: {vats - self.vats}.")


class LegalEntityVatSpider(BaseLegalEntitySpider):
    name = "legal-entity-vat-spider"
    type: Optional[Literal["vat", "date"]] = "vat"

    def start_requests(self) -> Iterable[Request]:
        """starting point for the scraper

        Makes a request for each vat number in `LEGAL_ENTITIES` between a given date range.
        This request is continued in the method `continue requests`.

        :yield: a scrapy Request per to-scrape legal entity.
        """
        for legal_entity in LEGAL_ENTITIES:
            url = self.format_url(legal_entity)
            legal_entity["vat"] = str(int(legal_entity["vat"]))
            yield Request(url=url, callback=self.parse, meta=legal_entity)


class LegalEntityDateSpider(BaseLegalEntitySpider):
    name = "legal-entity-date-spider"
    type: Optional[Literal["vat", "date"]] = "date"

    def __init__(self, *args, start_date: str, end_date: Optional[str] = None, **kwargs):
        super(LegalEntityDateSpider, self).__init__(*args, **kwargs)
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else date.today()

    def start_requests(self) -> Iterable[Request]:
        """starting point for the scraper

        Makes a request for each vat number in `LEGAL_ENTITIES` between a given date range.
        This request is continued in the method `continue requests`.

        :yield: a scrapy Request per to-scrape legal entity.
        """
        delta_days = self.end_date - self.start_date
        for i in range(delta_days.days + 1):
            scrape_date = self.start_date + timedelta(days=i)
            meta = {"start_date": scrape_date, "end_date": scrape_date, "page": 1}
            url = self.format_url(meta)
            yield Request(url=url, callback=self.parse, meta=meta)
