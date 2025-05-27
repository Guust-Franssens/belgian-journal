# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# ## Defining the schema
# Defining the schema upfront to ensure data quality.

# PARAMETERS CELL ********************

bronze_lh = notebookutils.lakehouse.get("LH_bronze").properties["abfsPath"]
silver_lh = notebookutils.lakehouse.get("LH_silver").properties["abfsPath"]
table_name = "belgian-journal"
table = f"{bronze_lh}/Tables/{table_name}"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

from pyspark.sql.types import StructType, StructField, StringType, DateType, BooleanType

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

# ## Creating the bronze table

# CELL ********************

empty_df = spark.createDataFrame([], schema)
empty_df.write.format("delta").mode("overwrite").option("overwriteSchema", "True").save(table)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Creating the silver table

# CELL ********************

empty_df = spark.createDataFrame([], schema)
empty_df.write.format("delta").mode("overwrite").option("overwriteSchema", "True").save(table)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
