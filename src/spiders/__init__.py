# This package will contain the spiders of your Scrapy project
#
# Please refer to the documentation for information on how to create and manage
# your spiders.

from src.spiders.legal_entities import BaseLegalEntitySpider, LegalEntityDateSpider, LegalEntityVatSpider

__all__ = [
    "BaseLegalEntitySpider",
    "LegalEntityDateSpider",
    "LegalEntityVatSpider",
]
