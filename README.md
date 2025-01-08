# Belgian Journal / Belgian Official Gazette / Belgisch Staatsblad / Moniteur Belge
Small pet project for playing around with [Belgian official journal](https://www.ejustice.just.fgov.be/cgi_tsv_pub/welcome.pl) (AKA Belgisch Staatsblad/Moniteur Belge). This repo implements a web-scraper to collect [company bylaws](https://corporatefinanceinstitute.com/resources/management/company-bylaws/), along with tools for text extraction and OCR (using Azure Document Intelligence), and summarization (using Azure OpenAI).

## Project setup
1. setup the environment by installing `uv` and installing the dependencies from [requirements.txt](./requirements.txt). See the [documentation of uv](https://docs.astral.sh/uv/) for more info.
2. setup the `.env` file by filling in the [.copy.env](.copy.env) and renaming it to `.env`
3. Ensure that all required resources are available within your azure environment:
    - **[Azure Blob Storage](https://learn.microsoft.com/en-us/azure/storage/blobs/)**: used for storing the publications
    - **[Azure AI Document Intelligence](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence)**: used for OCR, important that autoscaling is enabled
    - **[Azure Keyvault](https://learn.microsoft.com/en-us/azure/key-vault/)**: used for storing secrets like endpoints and resource names
    - **[User-Assigned Managed Identity](https://learn.microsoft.com/en-us/entra/identity/managed-identities-azure-resources/overview)**: technical user used in production which will be assigned to each created Azure Container Instance
    - **[Azure Container Registry](https://learn.microsoft.com/en-us/azure/container-registry/)**: store the docker container that will be used in production
    - **[Azure Automation](https://learn.microsoft.com/en-us/azure/automation/)**: used for scheduling and automation of scraper jobs. It is important that the automation Managed Identity has the right permissions in IAM to create and delete Azure Container Instances (ACI), access to container registry, access to log analytics and the ability to add the User-Assigned Managed Identity to the ACIs.
    - **[(optional) Azure Log analytics workspace](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/log-analytics-workspace-overview)**: used for storing logs
    - **[(optional) Azure OpenAI](https://learn.microsoft.com/en-us/azure/ai-services/openai/overview)**: used for summarizing publications


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
- [deployment](documentation/deployment.md)

## Visual overview
![](documentation/resources/solution.png)

## Publications dataset
On [Hugging Face](https://huggingface.co/datasets/guust-franssens/belgian-journal) you can find a dataset that was created by crawling with the legal-entity-date-spider.

## Deployment
This project can be easily hosted in [Azure Container Instances](https://learn.microsoft.com/en-gb/azure/container-instances/). A docker image containing all the dependencies can be created using the [Dockerfile](Dockerfile). In here, pip in combination with [requirements.txt](requirements.txt) is used to keep the image light.
A docker run can then be triggered using [Azure Automation](https://learn.microsoft.com/en-us/azure/automation/overview) with a 
[schedule](https://learn.microsoft.com/en-us/azure/automation/shared-resources/schedules) to create the Azure Container Instance and run the scraper for that day/month/year. For more info see the [documentation](documentation/deployment.md)
