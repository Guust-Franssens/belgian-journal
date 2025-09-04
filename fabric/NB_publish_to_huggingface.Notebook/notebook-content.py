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

# PARAMETERS CELL ********************

table_name = "belgian_journal"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

silver_lakehouse = notebookutils.lakehouse.get("LH_silver").properties["abfsPath"]
silver_table_path = f"{silver_lakehouse}/Tables/{table_name}"
variables = notebookutils.variableLibrary.getLibrary("VL_environment_variables")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

silver_table_path = "abfss://f259d7ab-0ec3-4190-b094-4cde9963712f@onelake.dfs.fabric.microsoft.com/1f4fd51b-d57a-44f4-b1f3-e34a6c7bef7c/Tables/belgian_journal"
df = spark.read.format("delta").load(silver_table_path).dropDuplicates()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

spark.conf.set("spark.sql.files.maxPartitionBytes", "524288000") 
df.filter(col("publication_date") < date(2025, 9, 1)).repartition(20).write.format("parquet").save(silver_lakehouse + f"/Files/{table_name}")
notebookutils.fs.rm(silver_lakehouse + f"/Files/{table_name}/_SUCCESS")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

token = notebookutils.credentials.getSecret(variables.key_vault_url, "token-huggingface")
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
    folder_path=f"/lakehouse/default/Files/{table_name}",
    path_in_repo="data",
    repo_type="dataset",
    commit_message="add June July August",
    create_pr=True,
    delete_patterns="*.parquet",
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
