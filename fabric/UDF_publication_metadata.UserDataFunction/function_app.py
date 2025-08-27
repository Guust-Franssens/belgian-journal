import re

import logging
import requests
import fabric.functions as fn
from bs4 import BeautifulSoup

udf = fn.UserDataFunctions()
base_url = "https://www.ejustice.just.fgov.be/cgi_tsv/rech_res.pl"

def parse_page(soup, url) -> dict:
    if not soup.find(string=re.compile(r"1\)[ a-zA-z]")):
        message = f"could not find anything for {url}"
        logging.warning(message)
        return {"company_juridical_form": None, "address": None, "act_description": None}

    first_publication_el = soup.find(string=re.compile(r"1\)[ a-zA-z]")).parent.parent
    company_juridical_form = first_publication_el.find("font").next_sibling.text.strip()
    blocks = list(first_publication_el.find("a", attrs={"class": "list-item--title"}).stripped_strings)
    logging.info(f"blocks found: {blocks}")
    if len(blocks) == 6:
        address, _, act_description, _, _, _ = blocks
    elif len(blocks) == 5:
        address, _, act_description, _, _ = blocks
    elif len(blocks) == 4:
        address, _, act_description, _ = blocks
    else:
        address = act_description = None

    return {"company_juridical_form": company_juridical_form, "address": address, "act_description": act_description}

def get_page(url) -> dict:
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.content)
    data = parse_page(soup, url)
    return data

@udf.function()
def get_publication_metadata(vat: str, publicationNumber: str) -> dict:
    url = base_url + f"?btw={vat}&numpu={publicationNumber}"
    logging.info(f"UDF triggered, fetching metadata from {url}")
    data = get_page(url)
    data["url"] = url
    return data