# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class LegalEntityItem(scrapy.Item):
    vat = scrapy.Field()  # vat number to which the publication belongs
    publication_id = scrapy.Field()  # id of the publication
    publication_date = scrapy.Field()  # date when publication was posted
    publication_meta = scrapy.Field()  # metadata of the publication
    file_url = scrapy.Field()  # single URL
    files = scrapy.Field()  # Metadata bout the downloaded file
