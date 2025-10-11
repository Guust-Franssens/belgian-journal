# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# # Notebook that sets up schema and downloads initial load from huggingface
# (instead of the download of HF, otherways to populate the table like shortcutting etc could be used.)

# CELL ********************

from pathlib import Path
from tqdm import tqdm

import requests
from datasets import load_dataset
from pyspark.sql.types import StructType, StructField, StringType, DateType, BooleanType

# https://milescole.dev/data-engineering/2024/09/17/To-V-Order-or-Not.html
spark.conf.set('spark.sql.parquet.vorder.default', 'false')

# https://blog.fabric.microsoft.com/en-us/blog/announcing-optimized-compaction-in-fabric-spark/
spark.conf.set('spark.databricks.delta.autoCompact.enabled', True)
spark.conf.set('spark.microsoft.delta.optimize.fast.enabled', True)
spark.conf.set('spark.microsoft.delta.optimize.fileLevelTarget.enabled', True)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Parameters

# PARAMETERS CELL ********************

table_name = "belgian_journal"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

bronze_lh = notebookutils.lakehouse.get("LH_bronze").properties["abfsPath"]
silver_lh = notebookutils.lakehouse.get("LH_silver").properties["abfsPath"]
bronze_table = f"{bronze_lh}/Tables/{table_name}"
bronze_staging = f"{bronze_table}_staging"
silver_table = f"{silver_lh}/Tables/{table_name}"
silver_staging = f"{silver_table}_staging"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Defining the schema
# Defining the schema upfront to ensure data quality.

# CELL ********************

schema = StructType([
    StructField('vat', StringType(), False),
    StructField('pubid', StringType(), False),
    StructField('act_description', StringType(), True),
    StructField('company_name', StringType(), False),
    StructField('company_juridical_form', StringType(), True),
    StructField('publication_date', DateType(), False),
    StructField('publication_number', StringType(), False),
    StructField('publication_link', StringType(), False),
    StructField('address', StringType(), True),
    StructField('street', StringType(), True),
    StructField('zipcode', StringType(), True),
    StructField('city', StringType(), True),
    StructField('is_digital', BooleanType(), False),
    StructField('text', StringType(), False),
])

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Creating the bronze tables and perform initial load
# 1. download the files from huggingface and upload it to the lakehouse files
# 2. load in the files with spark using the abfs path
# 3. save as a table in the lakehouse with the correct schema

# CELL ********************

# OneLake setup
headers = {
    "Authorization": "Bearer " + notebookutils.credentials.getToken("storage"),
    "Content-Type": "application/octet-stream"
}
workspace_id = notebookutils.runtime.getCurrentWorkspaceId()
lakehouse_id = notebookutils.lakehouse.get("LH_bronze").id
base_url = f"https://onelake.dfs.fabric.microsoft.com/{workspace_id}/{lakehouse_id}/Files/huggingface"

hf_repo_id = "guust-franssens/belgian-journal"
hf_api_url = f"https://huggingface.co/api/datasets/{hf_repo_id}/tree/main/data"

with requests.Session() as session:
    response = session.get(hf_api_url)
    response.raise_for_status()
    files = [
        f"https://huggingface.co/datasets/{hf_repo_id}/resolve/main/{f['path']}" 
        for f in response.json() if f["path"].endswith(".parquet")
    ]
    
    for f in tqdm(files):
        # Prepare OneLake file URL
        filename = Path(f).name
        onelake_url = f"{base_url}/{filename}"
        
        # Create file in OneLake
        response = requests.put(f"{onelake_url}?resource=file", headers=headers, data=b"", timeout=120)
        response.raise_for_status()
        
        # Stream from Hugging Face and upload to OneLake in chunks
        response = session.get(f, stream=True)
        response.raise_for_status()
        
        position = 0
        chunk_size = 5 * 1024 * 1024  # 5MB chunks
        
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                # Append chunk to OneLake
                append_response = requests.patch(
                    f"{onelake_url}?action=append&position={position}", 
                    headers=headers, 
                    data=chunk, 
                    timeout=600
                )
                append_response.raise_for_status()
                position += len(chunk)
        
        # Flush to finalize the file
        flush_response = requests.patch(f"{onelake_url}?action=flush&position={position}", headers=headers)
        flush_response.raise_for_status()


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

df = spark.read.format("parquet").load(f"{bronze_lh}/Files/huggingface/*.parquet", schema=schema)
df.write.format("delta").mode("overwrite").option("overwriteSchema", "True").save(bronze_table)
requests.delete(base_url + "?recursive=true", headers=headers)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

empty_df = spark.createDataFrame([], schema)
empty_df.write.format("delta").mode("overwrite").option("overwriteSchema", "True").save(bronze_staging)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Creating the silver tables

# CELL ********************

empty_df = spark.createDataFrame([], schema)
empty_df.write.format("delta").mode("overwrite").option("overwriteSchema", "True").save(silver_table)
empty_df.write.format("delta").mode("overwrite").option("overwriteSchema", "True").save(silver_staging)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
