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
Either you automate this task with something like Github CI/CD, Azure Automation, ... or you run it manually from azure CLI. In both cases it's important to specify the restart-policy to be never because by defaults it restarts the container after an error or exit (the scraper will exit after collecting all publications).

### Running manually
```bash
RESOURCE_GROUP="my-resource-group"
ACR_NAME="acrbelgianjournal"
IMAGE_NAME="belgian-journal"
ACI_NAME="belgian-journal-october"
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

### Fully automated (production)
Azure Automation allows to schedule a powershell script, this is ideal as each day an Azure Container Instance needs to be created (to run the scraper for that day), and any previously ran scraper jobs need to be deleted. User-assigned Managed Identity (think technical user) is used for authentication and authorization, thus the ACI that is created needs to be assigned to this technical user in order to access key vault, blob storage and cognitive services OCR.

```powershell
# Calculate the start and end dates dynamically (here it is based on daily scraping however can be weekly, monthly, yearly...)
$START_DATE = (Get-Date).ToString("yyyy-MM-dd")
$END_DATE = (Get-Date).ToString("yyyy-MM-dd")

# Generate dynamic ACI_NAME based on the current date (again can be named after the week, month, year...)
$ACI_NAME = "ACI-belgian-journal-" + (Get-Date).ToString("yyyy-MM-dd")

# Fetch credentials for container registry and log analytics (log analytics is optional but recommended for spotting errors)
$RESOURCE_GROUP = "belgian-journal"
$ACR_NAME = "acrbelgianjournal"
$ACR_PASSWORD = "..."
$IMAGE_NAME = "belgian-journal"
$LOG_ANALYTICS_WORKSPACE_ID = "..."
$LOG_ANALYTICS_WORKSPACE_KEY = "..."

# Create the new ACI
az container create `
  --resource-group $RESOURCE_GROUP `
  --name $ACI_NAME `
  --image "$ACR_NAME.azurecr.io/$IMAGE_NAME:latest" `
  --registry-login-server "$ACR_NAME.azurecr.io" `
  --registry-username $ACR_NAME `
  --registry-password $ACR_PASSWORD `
  --log-analytics-workspace $LOG_ANALYTICS_WORKSPACE_ID `
  --log-analytics-workspace-key $LOG_ANALYTICS_WORKSPACE_KEY `
  --command-line "scrapy crawl legal-entity-date-spider -a start_date=$START_DATE -a end_date=$END_DATE" `
  --cpu 1 `
  --memory 2 `
  --os-type Linux `
  --restart-policy Never

# Cleanup older ACIs
$oldACIs = az container list --resource-group $RESOURCE_GROUP --query "[?contains(name, 'ACI-belgian-journal-') && provisioningState=='Succeeded']" --output json | ConvertFrom-Json
foreach ($aci in $oldACIs) {
    az container delete --resource-group $RESOURCE_GROUP --name $aci.name --yes
}
```