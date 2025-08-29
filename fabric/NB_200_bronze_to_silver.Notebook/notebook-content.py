# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# ## Bronze to silver notebook
# Ensures that empty strings are converted to null values


# CELL ********************

from datetime import date

from pyspark.sql.functions import col, when, max
from delta.tables import DeltaTable

# https://milescole.dev/data-engineering/2024/09/17/To-V-Order-or-Not.html
spark.conf.set('spark.sql.parquet.vorder.default', 'false')

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

bronze_lakehouse = notebookutils.lakehouse.get("LH_bronze").properties["abfsPath"]
silver_lakehouse = notebookutils.lakehouse.get("LH_silver").properties["abfsPath"]
bronze_table_path = f"{bronze_lakehouse}/Tables/{table_name}"
silver_table_path = f"{silver_lakehouse}/Tables/{table_name}"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Read latest changes from bronze and merge (insert) into silver table

# CELL ********************

max_date = spark.read.format("delta").load(silver_table_path).select("publication_date").agg(max("publication_date")).collect()[0][0] 
max_date = max_date or date(1900, 1, 1)
max_date

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

new_records = (
    spark.read.format("delta").load(bronze_table_path)
    .filter(col("publication_date") >= max_date)
    .withColumn("address", when(col("address") == "", None).otherwise(col("address")))
    .withColumn("act_description", when(col("act_description") == "", None).otherwise(col("act_description")))
    .withColumn("company_juridical_form", when(col("company_juridical_form") == "", None).otherwise(col("company_juridical_form")))
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

silver_table = DeltaTable.forPath(spark, silver_table_path)
silver_table.alias("s").merge(new_records.alias("n"), "s.vat = n.vat AND s.pubid = n.pubid").whenNotMatchedInsertAll().execute()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
