"""
scrapes legal entities from the following web page:
https://www.ejustice.just.fgov.be/cgi_tsv/rech.pl
"""

from datetime import date
from typing import Iterable, Optional

import scrapy
from scrapy.http import Request, Response

# list of company numbers (VAT number minus BE) to scrape
LEGAL_ENTITIES = [
    {"vat": "0471938850", "start_date": date(year=1998, month=7, day=29), "end_date": date.today()},  # EY consulting
    {"vat": "0463318421", "start_date": None, "end_date": None},  # NORRIQ Belgium
]


class LegalEntitySpider(scrapy.Spider):
    name = "legal-entity"
    base_url = "https://www.ejustice.just.fgov.be"
    acts = {
        "": ("leeg", "vide"),
        "c01": (
            "rubriek oprichting (nieuwe rechtspersoon, opening bijkantoor, enz...)",
            "rubrique constitution (nouvelle personne morale, ouverture succursale, etc...)",
        ),
        "c02": (
            "rubriek einde (stopzetting, intrekking stopzetting, nietigheid, ger. ak., gerechtelijke reorganisatie, enz...)",
            "rubrique fin (cessation, annulation cessation, nullité, conc, réorganisation judiciaire, etc...)",
        ),
        "c03": ("benaming", "dénomination"),
        "c04": ("maatschappelijke zetel", "siège social"),
        "c05": (
            "adressen anders dan maatschappelijke zetel",
            "adresse autre que siège social",
        ),
        "c06": ("doel", "objet"),
        "c07": ("kapitaal - aandelen", "capital, actions"),
        "c08": ("ontslagen - benoemingen", "démissions, nominations"),
        "c09": ("algemene vergadering", "assemblée générale"),
        "c10": ("boekjaar", "année comptable"),
        "c11": (
            "statuten (vertaling, coördinatie, overige wijzigingen, enz...)",
            "Statuts (traduction, coordination, autres modifications)",
        ),
        "c12": ("wijziging rechtsvorm", "modification forme juridique"),
        "c13": (
            "rubriek herstructurering (fusie, splitsing, overdracht vermogen, enz...)",
            "rubrique restructuration  (fusion, scission, transfert patrimoine, etc...)",
        ),
        "c14": ("jaarrekeningen", "comptes annuels"),
        "c15": ("diversen", "divers"),
        "c16": ("ambtshalve doorhaling  KBO nr.", "radiation d'office n° BCE"),
    }

    def start_requests(self) -> Iterable[Request]:
        """starting point for the scraper

        Makes a request for each vat number in `LEGAL_ENTITIES` between a given date range.
        This request is continued in the method `continue requests`.

        :yield: a scrapy Request per to-scrape legal entity.
        """
        for legal_entity in LEGAL_ENTITIES:
            vat = legal_entity["vat"]
            start_date = legal_entity["start_date"].strftime("%Y-%m-%d") if legal_entity["start_date"] else ""
            end_date = legal_entity["end_date"].strftime("%Y-%m-%d") if legal_entity["start_date"] else ""
            meta = {"vat": vat, "start_date": start_date, "end_date": end_date}
            url = f"{self.base_url}/cgi_tsv/rech_res.pl?language=nl&btw={vat}&pdd={start_date}&pdf={end_date}"
            yield Request(url=url, callback=self.continue_request, meta=meta)

    def continue_request(self, response: Response) -> Optional[Iterable[Request]]:
        """Checks if there are any publications found for this legal entity.
        If yes: do an additional request per publication category
        If not: finished scraping this legal entity

        :param response: scrapy.Response
        :return: None if no publications for this legal entity
        :yield: a scrapy Request per publication category
        """
        any_publications = "Geen tekst komt overeen met uw zoekopdracht" not in response.text
        if not any_publications:
            self.logger.debug(f"No publications found for {response.url}")
            return None

        for act in self.acts.keys():
            meta = response.meta
            meta["act"] = act
            yield scrapy.Request(url=response.url + f"&akte={act}", callback=self.parse, meta=meta)

    def parse(self, response: Response) -> Optional[Iterable[Request]]:
        """Parses the page per act per legal entity and extracts the publication div elements

        :param response: scrapy.Response
        :yield: a scrapy Request per publication category OR Item
        :return: None when no div elements are found in this act
        """
        any_publications = "Geen tekst komt overeen met uw zoekopdracht" not in response.text
        if not any_publications:
            return None

        # list of publication elements per legal entity per act
        publication_elements = response.xpath("/html/body/div/div[4]/div/main/div[2]/div/div[*]").getall()

        if len(publication_elements) == 100:  # max number of publication elements on a page
            meta = response.meta
            meta["page_number"] = response.meta.get("page_number", 2)
            meta["publication_elements"] = response.meta.get("publication_elements", []) + publication_elements
            continue_url = (
                f"{self.base_url}/cgi_tsv/list.pl?language=nl&btw{meta['vat']}"
                f"&pdd={meta['start_date']}&pdf={meta['end_date']}"
                f"&akte={meta['act']}&page={meta['page_number']}"
            )
            self.logger.debug(f"100 publications on page {response.url}, continueing on {continue_url}")
            yield scrapy.Request(continue_url, callback=self.parse, meta=meta)

        else:  # fetched all publication elements
            publication_elements += response.meta.get("publication_elements", [])
            self.logger.info(f"Found {len(publication_elements)} for vat: {response.meta.get('ben')}")
            yield from self.parse_publications(publication_elements, response.meta)

    def parse_publications(self, publication_elements: scrapy.selector.unified.SelectorList, meta: dict):
        """Creates a scrapy ItemLoader such that the PDFs get downloaded
        This method gets called multiple times, once per act that contains pdfs

        :param publication_elements: all publication elements found for the legal entity for the given filters
        :param meta: response.meta from previous request
        """
        raise NotImplementedError
