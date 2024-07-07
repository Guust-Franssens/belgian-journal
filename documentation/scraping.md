# Design choices
In this repo we are interested in scraping dedicated companies, rather than scraping all publications. Depending on your interest, you would approach scraping diffrently.

## Scraping specific VAT numbers
When the interest is in scraping specific companies, you alter the url with adding `?btw=...`, to get something like `https://www.ejustice.just.fgov.be/cgi_tsv/rech_res.pl?btw=0471938850`. You can also scrape between two dates by adding a start- and end-date, e.g.: `https://www.ejustice.just.fgov.be/cgi_tsv/rech_res.pl?btw=0471938850&pdd=1998-07-29&pdf=2024-06-02`. However this get requests take much longer to respond when adding filters other than the VAT number, indicating that the back-end of the site has the VAT column indexed. [Response time testing](documentation/scraping.ipynb)

|  VAT search |  VAT + other filter search |
|---|---|
| ~ 202 ms  | ~ 7.01 s |

## Scraping specific day
The site does not require specifiying a VAT number. To get all publications for 4th of July 2024, the URL must be modified to the following `https://www.ejustice.just.fgov.be/cgi_tsv/rech_res.pl?pdd=2024-07-04&pdf=2024-07-04`. Now usually there will be several pages of publications (100 per page), thus the scraper would have to traverse all pages until no more publications are found.