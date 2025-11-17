# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "jupyter",
# META     "jupyter_kernel_name": "python3.11"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# ## Incrementally load Blobs to bronze lakehouse
# Use python notebook as mainly APIs are called and the data is not large.

# CELL ********************

import base64
import time
import json

import asyncio
import pandas as pd
import requests
from azure.core.credentials import AccessToken
from azure.storage.blob.aio import BlobServiceClient as AsyncBlobServiceClient
from deltalake import DeltaTable, write_deltalake
from tqdm import tqdm


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# MARKDOWN ********************

# ## Define parameters

# PARAMETERS CELL ********************

table_name = "belgian_journal"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# CELL ********************

bronze_lakehouse = notebookutils.lakehouse.get("LH_bronze").properties["abfsPath"]
table_path = f"{bronze_lakehouse}/Tables/{table_name}_staging"

try:
    variables = notebookutils.variableLibrary.getLibrary("VL_environment_variables")
    storage_account_url = variables.storage_account_url
    update_blobs = variables.update_blobs
except:
    # bunch of code as notebookutils.variableLibrary.getLibrary currently doesn't work when the notebook is triggered from a pipeline?
    workspace_id = notebookutils.runtime.context["currentWorkspaceId"]
    url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/VariableLibraries"
    headers = {"Authorization": f"Bearer {notebookutils.credentials.getToken('pbi')}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()["value"][0]
    vl_id = data["id"]
    vl_active_value_set_name = data["properties"]["activeValueSetName"]
    vl_id, vl_active_value_set_name

    url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/VariableLibraries/{vl_id}/getDefinition"
    response = requests.post(url, headers=headers)
    response.raise_for_status()
    if response.status_code == 202:
        sleep_time = int(response.headers["Retry-After"])
        print(f"sleeping for {sleep_time} seconds")
        time.sleep(sleep_time)
        response = requests.get(response.headers["Location"], headers=headers)
        response.raise_for_status()
        response = requests.get(response.headers["Location"], headers=headers)
        response.raise_for_status()

    parts = response.json()["definition"]["parts"]
    for part in parts:
        part["payload"] = json.loads(base64.b64decode(part["payload"]))
    variable_sets = {part["path"]: part["payload"] for part in parts}
    variables = {var["name"]: var["value"] for var in variable_sets.get("variables.json").get("variables", [])}
    variables.update({var["name"]: var["value"] for var in variable_sets.get(f"valueSets/{vl_active_value_set_name}.json", {}).get("variableOverrides", [])})

    storage_account_url = variables.get("storage_account_url")
    update_blobs = variables.get("update_blobs")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# MARKDOWN ********************

# ## Create a custom token since identity authentication does not work (yet)

# CELL ********************

class TokenCredential:
    token = None
    expires_on = None

    def _get_token(self):
        self.token = notebookutils.credentials.getToken("storage")
        self.expires_on = int(time.time()) + 3600

    def get_token(self, *args, **kwargs):
        if not self.token or (self.expires_on and time.time() < self.expires_on):
            self._get_token()
    
        return AccessToken(self.token, self.expires_on)

credential = TokenCredential()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# MARKDOWN ********************

# ## Fetch all unprocessed Blobs

# CELL ********************

async_blob_service_client = AsyncBlobServiceClient(account_url=storage_account_url, credential=credential)
async_container_client = async_blob_service_client.get_container_client("belgian-journal")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# CELL ********************

tasks = []
batch_size = 500
publications = {}

async def download_blob(blob_name):
    async_blob_client = async_container_client.get_blob_client(blob_name)
    stream = await async_blob_client.download_blob()
    data = await stream.readall()
    publications[blob_name] = json.loads(data)

async for blob in async_container_client.find_blobs_by_tags("status='unprocessed'"):
    tasks.append(asyncio.create_task(download_blob(blob["name"])))

    if len(tasks) >= batch_size:
        await asyncio.gather(*tasks)
        tasks.clear()
    
if tasks:
    await asyncio.gather(*tasks)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# MARKDOWN ********************

# ## Ingest into lakehouse

# CELL ********************

storage_options = {"bearer_token": notebookutils.credentials.getToken('storage'), "use_fabric_endpoint": "true"}
dt = DeltaTable(table_path, storage_options=storage_options)
columns = [field.name for field in dt.schema().fields]


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# CELL ********************

# ensure correct dtypes for date and potential null columns
df = pd.DataFrame(publications.values(), columns=columns)
df["publication_date"] = pd.to_datetime(df["publication_date"], format="%Y-%m-%d").dt.date
df["street"] = df["street"].astype("string")
df["zipcode"] = df["zipcode"].astype("string")
df["city"] = df["city"].astype("string")
df.head()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# CELL ********************

df.publication_date.min()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# CELL ********************

storage_options = {"bearer_token": notebookutils.credentials.getToken("storage"), "use_fabric_endpoint": "true"}
write_deltalake(table_path, df, mode='overwrite', schema_mode=None, engine='rust', storage_options=storage_options)
dt.vacuum()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# MARKDOWN ********************

# ## Update BLOBs to indicate that they are now processed

# CELL ********************

tasks = []
batch_size = 500

async def update_blob(blob_name):
    blob_client = async_container_client.get_blob_client(blob_name)
    tags = await blob_client.get_blob_tags()
    tags["status"] = "processed"
    await blob_client.set_blob_tags(tags)

if update_blobs:
    for publication in tqdm(publications):
        tasks.append(asyncio.create_task(update_blob(publication)))

        if len(tasks) >= batch_size:
            await asyncio.gather(*tasks)
            tasks.clear()

if tasks:
    await asyncio.gather(*tasks)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# CELL ********************

blobs = []
async for blob in async_container_client.find_blobs_by_tags("status='unprocessed'"):
    blobs.append(blob)
len(blobs)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }
