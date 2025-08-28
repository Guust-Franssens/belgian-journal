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

# ## Second transformation notebook for Bronze to Silver
# Here we leverage User Data Functions to retrieve the missing data. This can happen in Python as only a small subsection of the dataset is used (the ones with missing values).

# CELL ********************

import concurrent.futures
from datetime import datetime, date, timedelta

import requests
import pyarrow.dataset as ds
from deltalake import DeltaTable, write_deltalake
from tqdm import tqdm

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# MARKDOWN ********************

# ## Parameters

# PARAMETERS CELL ********************

table_name = "belgian_journal"


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# CELL ********************

workspaceId = notebookutils.runtime.context["currentWorkspaceId"]
silver_lakehouse = notebookutils.lakehouse.get("LH_silver").properties["abfsPath"]
table_path = f"{silver_lakehouse}/Tables/{table_name}"
table_path_staging = f"{silver_lakehouse}/Tables/{table_name}_staging"


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# MARKDOWN ********************

# ## Define User-Data-Function (UDF)

# CELL ********************

token = notebookutils.credentials.getToken('pbi')
url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/items?type=UserDataFunction"
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(url, headers=headers)
response.raise_for_status()
udfId = response.json()["value"][0]["id"]

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# MARKDOWN ********************

# ## Fetch publications that are missing metadata

# CELL ********************

storage_options = {"bearer_token": notebookutils.credentials.getToken('storage'), "use_fabric_endpoint": "true"}
dt = DeltaTable(table_path, storage_options=storage_options)
filter_expression = (
    ds.field("company_juridical_form").is_null() |
    ds.field("act_description").is_null() |
    ds.field("address").is_null()
)
df = dt.to_pyarrow_dataset().scanner(filter=filter_expression).to_table().to_pandas(date_as_object=False)
df = df[df["publication_date"] <= datetime.now() - timedelta(days=7)]

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# MARKDOWN ********************

# ## For each publication get the metadata via the UDF

# CELL ********************

udfName = "get_publication_metadata"
url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/userDataFunctions/{udfId}/functions/{udfName}/invoke"
def get_metadata(vat: str, publication_number: str):
    token = notebookutils.credentials.getToken('pbi')
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    request_body = {"vat": vat, "publicationNumber": publication_number}
    response = requests.post(url, json=request_body, headers=headers)
    return response.json()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# CELL ********************

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    futures = {executor.submit(get_metadata, row.vat, row.publication_number): i for i, row in df.iterrows()}
    for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures)):
        result = future.result()
        index = futures[future]
        if result.get("status") == "Succeeded":
            output = result["output"]
            output.pop("url", None)
            columns = list(output.keys())
            values = list(output.values())
            df.loc[index, columns] = values


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }

# MARKDOWN ********************

# ## Write to OneLake to temporary updates table

# CELL ********************

storage_options = {"bearer_token": notebookutils.credentials.getToken("storage"), "use_fabric_endpoint": "true"}
mask = (df["company_juridical_form"].notna()) & (df["act_description"].notna()) & (df["address"].notna())
write_deltalake(
    table_or_uri=table_path_staging, 
    data=df[mask],
    schema=dt.schema(),
    mode="overwrite",
    schema_mode="overwrite",
    engine='rust',
    storage_options=storage_options
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "jupyter_python"
# META }
