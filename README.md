# Belgian Official Journal
Small pet project for playing around with [Belgian official journal](https://www.ejustice.just.fgov.be/cgi_tsv_pub/welcome.pl) (AKA Belgisch Staatsblad/Moniteur Belge).

## Project setup
1. setup the environment by installing [environment.yml](environment.yml)<br>
`conda install -n belgian-journal -f environment.yml`
2. setup the `.env` file by filling in the [.myenv](.myenv) and renaming it to `.env`

## Running the project
There are two spiders in this repo that can be used to crawl the Belgian Journal.
1. `legal-entity-vat-spider`: takes a list of vats to scrape
2. `legal-entity-date-spider`: takes a daterange between which it will scrape (dates included)

Activate the virtual environment and then run `scrapy crawl legal-entity-vat-spider` or `scrapy crawl legal-entity-date-spider -a start_date=2023-01-01 -a end_date=2023-01-07`.

## Documentation
There is additional documentation on this project for the following topics:
- [scraping](documentation/scraping.md)
- [OCR](documentation/ocr.md)
- [text extraction](documentation/extract_text.md)
- [summarization](documentation/summarize.md)

## Visual overview
![](documentation/resources/solution.png)
