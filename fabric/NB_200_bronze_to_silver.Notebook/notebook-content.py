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
# Transformations performed:
# - convert empty strings to null values
# - fill in blank values with updated values

# CELL ********************

from pyspark.sql.functions import col, when
from delta.tables import DeltaTable

# https://milescole.dev/data-engineering/2024/09/17/To-V-Order-or-Not.html
spark.conf.set('spark.sql.parquet.vorder.default', 'false')

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# PARAMETERS CELL ********************

bronze_lakehouse = notebookutils.lakehouse.get("LH_bronze").properties["abfsPath"]
silver_lakehouse = notebookutils.lakehouse.get("LH_silver").properties["abfsPath"]
table_name = "belgian-journal"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

original = DeltaTable.forPath(spark, silver_lh + f"/Tables/{table_name}")
updated_df = original.toDF() \
    .filter((col("address") == "") | (col("act_description") == "") | (col("company_juridical_form") == "")) \
    .withColumn("address", when(col("address") == "", None).otherwise(col("address"))) \
    .withColumn("act_description", when(col("act_description") == "", None).otherwise(col("act_description"))) \
    .withColumn("company_juridical_form", when(col("company_juridical_form") == "", None).otherwise(col("company_juridical_form")))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

original.alias("t") \
    .merge(updated_df.alias("u"), "t.vat = u.vat AND t.pubid = u.pubid") \
    .whenMatchedUpdate(set={
        "address": col("u.address"),
        "act_description": col("u.act_description"),
        "company_juridical_form": col("u.company_juridical_form")
    }).execute()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
