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

bronze_lh = "abfss://0d3ad52f-64d5-4aa9-9da2-3a326f988d8f@onelake.dfs.fabric.microsoft.com/6acc47f3-3745-4fc2-9ac2-52ad2d91c117"
table = f"{bronze_lh}/Tables/belgian-journal"

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

# CELL ********************

empty_df = spark.createDataFrame([], schema)
empty_df.write.format("delta").mode("overwrite").option("overwriteSchema", "True").save(table)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
