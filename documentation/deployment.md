# Deploying the project

As publications are published on a daily basis, the scraper has to run periodically to keep up to date. The scraper can be setup to run daily/weekly/monthly and run within a container instance that will scrape that specific period. 

## Building the docker image
```bash
export IMAGE_NAME="belgian-journal"
docker build -t "${IMAGE_NAME}:latest" .
```

Now that the docker image is build, it needs to be pushed to a container registry where it will be saved. For this, [azure container registry](https://learn.microsoft.com/en-us/azure/container-registry/container-registry-intro) can be used. After logging in, you should tag the image to that server and push it.

```bash
export ACR_NAME="acrbelgianjournal"
docker tag "${IMAGE_NAME}:latest" "${ACR_NAME}.azurecr.io/${IMAGE_NAME}:latest"
docker push "${ACR_NAME}.azurecr.io/${IMAGE_NAME}:latest"
```

## Running the scraper in Azure Container Instances
Either you automate this task with something like Github CI/CD, Azure Functions, ... or you run it manually from azure CLI. In both cases it's important to specify the restart-policy to be never because by defaults it restarts the container after an error or exit.

### Running manually
```bash
RESOURCE_GROUP="my-resource-group"
ACR_NAME=acrbelgianjournal
IMAGE_NAME=belgian-journal
ACI_NAME=belgian-journal-october
START_DATE="2024-10-01"
END_DATE="2024-10-31"
ACR_USER="my-user"
ACR_PASSWORD="my-password"

az container create \
  --resource-group $RESOURCE_GROUP \
  --name $ACI_NAME \
  --image acrbelgianjournal.azurecr.io/$IMAGE_NAME:latest \
  --registry-login-server acrbelgianjournal.azurecr.io \
  --registry-username $ACR_USER \
  --registry-password $ACR_PASSWORD \
  --command-line "scrapy crawl legal-entity-date-spider -a start_date=$START_DATE -a end_date=$END_DATE" \
  --cpu 1 \
  --memory 2 \
  --os-type Linux \
  --restart-policy Never
```

### Azure functions
To be written.