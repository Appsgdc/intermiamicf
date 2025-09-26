{{ config(materialized="incremental", unique_key="customer_id",tags=["customer_sales_pipeline"]) }}

select * from {{ source("Redshift-stage", "dim_customer") }}

