# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# ## This notebook merges the updates performed by NB_201 into delta lake

# CELL ********************

from delta.tables import DeltaTable

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

silver_lakehouse = notebookutils.lakehouse.get("LH_silver").properties["abfsPath"]
table_name = "belgian-journal"
updates_table_name = f"{table_name}-updates"
silver_table_path = f"{silver_lakehouse}/Tables/{table_name}"
updates_table_path = f"{silver_lakehouse}/Tables/{updates_table_name}"


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

df_updates = spark.read.format("delta").load(updates_table_path)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

silver_table = DeltaTable.forPath(spark, silver_table_path)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

silver_table.alias("target")\
    .merge(source=df_updates.alias("source"), condition="target.vat = source.vat AND target.pubid = source.pubid")\
    .whenMatchedUpdate(set={"address": "source.address", "act_description": "source.act_description", "company_juridical_form": "source.company_juridical_form"})\
    .execute()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
