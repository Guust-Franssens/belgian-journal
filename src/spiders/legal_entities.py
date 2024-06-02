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
    "0471938850",  # EY consulting
]
# filters publications between start & end-date (includes that day)
START_DATE: Optional[date] = date(year=1998, month=7, day=29)
# START_DATE: Optional[date] = None
END_DATE: Optional[date] = date.today()


class LegalEntitySpider(scrapy.Spider):
    name = "legal-entity"
    base_url = "https://www.ejustice.just.fgov.be"
    start_date = START_DATE.strftime("%Y-%m-%d") if START_DATE else ""
    end_date = END_DATE.strftime("%Y-%m-%d") if END_DATE else ""
    acts = {
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

        :yield: a scrapy Request per to-scrape legal entity.
        """
        for legal_entity in LEGAL_ENTITIES:
            url = f"{self.base_url}/cgi_tsv/rech_res.pl?language=nl&btw={legal_entity}&pdd={self.start_date}&pdf={self.end_date}"
            yield Request(url=url, callback=self.continue_request, encoding="latin-1")

    def continue_request(self, response: Response) -> Optional[Iterable[Request]]:
        """Checks if there are any publications found for this legal entity.
        If yes: do an additional request per publication category
        If not: finished scraping this legal entity

        :param response: _description_
        :return: None if no publications for this legal entity
        :yield: a scrapy Request per publication category
        """
        pdfs = response.xpath("/html/body/div/div[4]/div/main/div[2]/div/div[*]/div/a/font/a/@href").getall()
        for pdf in pdfs:
            print(self.base_url + pdf)
