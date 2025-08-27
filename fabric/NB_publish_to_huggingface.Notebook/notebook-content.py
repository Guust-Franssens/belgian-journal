# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "534c5354-9736-44f7-a5f7-18cffa19e7f0",
# META       "default_lakehouse_name": "LH_silver",
# META       "default_lakehouse_workspace_id": "fb307c54-91c8-4436-a72e-da0c67a2d491",
# META       "known_lakehouses": [
# META         {
# META           "id": "534c5354-9736-44f7-a5f7-18cffa19e7f0"
# META         }
# META       ]
# META     }
# META   }
# META }

# CELL ********************

from datetime import datetime, date

import datasets
from huggingface_hub import HfApi, login
from pyspark.sql.functions import col

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

silver_lakehouse = notebookutils.lakehouse.get("LH_silver").properties["abfsPath"]
table_name = "belgian-journal"
silver_table_path = f"{silver_lakehouse}/Tables/{table_name}"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

df = spark.read.format("delta").load(silver_table_path)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

df2 = spark.read.format("delta").load("abfss://30953eab-1865-42f8-a9f5-9c644079f1c3@onelake.dfs.fabric.microsoft.com/9f317ee6-48b0-4c36-b84e-100c370be617/Tables/belgian-journal")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

df_all = df.union(df2).dropDuplicates()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

spark.conf.set("spark.sql.files.maxPartitionBytes", "524288000") 
df_all.filter(col("publication_date") < date(2025, 6, 1)).repartition(20).write.format("parquet").save(silver_lakehouse + f"/Files/{table_name}")
notebookutils.fs.rm(silver_lakehouse + f"/Files/{table_name}/_SUCCESS")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

token = notebookutils.credentials.getSecret("https://kv-fabric-belux.vault.azure.net/", "token-huggingface")
login(token)
api = HfApi()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

api.upload_folder(
    repo_id="guust-franssens/belgian-journal",
    folder_path="/lakehouse/default/Files/belgian-journal",
    path_in_repo="data",
    repo_type="dataset",
    commit_message="add march april may",
    create_pr=True,
    delete_patterns="*.parquet",
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
