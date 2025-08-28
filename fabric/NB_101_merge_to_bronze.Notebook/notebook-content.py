# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# ## This notebook merges the staging table containing updates into the bronze table

# CELL ********************

from delta.tables import DeltaTable

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Define parameters

# PARAMETERS CELL ********************

table_name = "belgian_journal"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

bronze_lakehouse = notebookutils.lakehouse.get("LH_bronze").properties["abfsPath"]
bronze_table_path = f"{bronze_lakehouse}/Tables/{table_name}"
staging_table_path = f"{bronze_table_path}_staging"


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Read and merge data into bronze

# CELL ********************

df_staging = spark.read.format("delta").load(staging_table_path)
bronze_table = DeltaTable.forPath(spark, bronze_table_path)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

bronze_table.alias("target")\
    .merge(source=df_staging.alias("source"), condition="target.vat = source.vat AND target.pubid = source.pubid")\
    .whenNotMatchedInsertAll()\
    .execute()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
