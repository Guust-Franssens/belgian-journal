"""
scrapes legal entities from the following web page:
https://www.ejustice.just.fgov.be/cgi_tsv/rech.pl
"""

import re
from datetime import date, datetime
from pathlib import Path
from typing import Generator, Iterable, Literal, Optional, Tuple, Union

import scrapy
from azure.storage.blob import BlobServiceClient
from scrapy.http import Request, Response
from scrapy.selector.unified import SelectorList
from scrapy.utils.project import get_project_settings

from src.items import LegalEntityItem

SETTINGS = get_project_settings()
AZURE_STORAGE_ACCOUNT_URL = SETTINGS["AZURE_STORAGE_ACCOUNT_URL"]
AZURE_STORAGE_ACCOUNT_KEY = SETTINGS["AZURE_STORAGE_ACCOUNT_KEY"]
AZURE_CONTAINER_NAME = SETTINGS["AZURE_CONTAINER_NAME"]

# list of company numbers (VAT number minus BE) to scrape
LEGAL_ENTITIES = [
    {"vat": "0471938850", "start_date": date(year=1998, month=7, day=29), "end_date": date.today()},  # EY consulting
    {"vat": "0463318421", "start_date": None, "end_date": None},  # NORRIQ Belgium
]


class LegalEntitySpider(scrapy.Spider):
    name = "legal-entity-spider"
    base_url = "https://www.ejustice.just.fgov.be"
    blob_service_client = BlobServiceClient(AZURE_STORAGE_ACCOUNT_URL, AZURE_STORAGE_ACCOUNT_KEY)
    container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)

    def start_requests(self) -> Iterable[Request]:
        """starting point for the scraper

        Makes a request for each vat number in `LEGAL_ENTITIES` between a given date range.
        This request is continued in the method `continue requests`.

        :yield: a scrapy Request per to-scrape legal entity.
        """
        for legal_entity in LEGAL_ENTITIES:
            url = self.format_url(legal_entity)
            yield Request(url=url, callback=self.parse, meta=legal_entity)

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
        publication_elements: SelectorList = response.xpath("/html/body/div/div[4]/div/main/div[2]/div/div[*]")

        # process elements on page by collecting publication elements
        if publication_elements:
            meta["publication_elements"] = response.meta.get("publication_elements", []) + publication_elements

        # max number of publication elements on a page = 100, in this case next page needs to be crawled
        if len(publication_elements) == 100:
            meta["page"] = response.meta.get("page", 1) + 1
            url = self.format_url(meta)
            self.logger.debug(f"100 publications on page {response.url}, continueing on next page {meta['page']}")
            yield scrapy.Request(url, callback=self.parse, meta=meta)
        else:
            yield from self.parse_publications(meta)

    def parse_publications(self, meta: dict) -> Iterable[scrapy.Item]:
        """Creates a scrapy ItemLoader such that the PDFs get downloaded
        This method gets called multiple times, once per act that contains pdfs

        :param publication_elements: all publication elements found for the legal entity for the given filters
        :param meta: response.meta from previous request
        """
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
            city, zipcode, street = self.extract_address(address)
            publication_date, publication_number = self.extract_publication_date_and_number(pub_date_and_number)

            if publication_date and publication_date <= pub_date_threshold:
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
                "vat": meta["vat"],
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
                vat=meta["vat"],
                publication_id=pubid,
                publication_number=publication_number,
                publication_date=publication_date,
                publication_meta=publication_meta,
                file_urls=[pdf_absolute_url],
            )
            yield item

    def closed(self, reason: Literal["finished", "cancelled", "cancelled"]) -> None:
        """Called whenever the spider gets closed

        :param reason: reason of the closing of the spider
        """
        if reason != "finished":
            return

        self.logger.info("Successfully finished scraping run.")

    def format_url(self, meta: dict[str, Union[str, int]]) -> str:
        """creates the to-scrape url based on the meta

        :param meta: _description_
        :return: _description_
        """
        page = meta.get("page")
        if page:
            url = f"{self.base_url}/cgi_tsv/list.pl?language=nl&page={str(page)}"
        else:
            url = f"{self.base_url}/cgi_tsv/rech_res.pl?language=nl"
        url += f"&btw={meta.get('vat', '')}"
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
            self.logger.warning(
                f"Could not extract street, zipcode and city from address: '{address}'. "
                "Defaulting to setting the address section to the city attribute."
            )
            city = address
            street = zipcode = None

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
