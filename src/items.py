# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class LegalEntityItem(scrapy.Item):
    vat = scrapy.Field()  # vat number to which the publication belongs
    publication_id = scrapy.Field()  # id of the publication pdf (found in the url)
    publication_number = scrapy.Field()  # publication number (found in the metadata section)
    publication_date = scrapy.Field()  # date when publication was posted
    publication_meta = scrapy.Field()  # metadata of the publication
    file_urls = scrapy.Field()  # single URL
    files = scrapy.Field()  # Metadata bout the downloaded file
    file_path = scrapy.Field()  # location of the donwloaded pdf
