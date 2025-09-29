select *
from `dev.public.AR_RECEIPT_METHODS`
{% if is_incremental() %}
  where LASTUPDATEDATE >= (
    select coalesce(max(LASTUPDATEDATE), timestamp('1900-01-01 00:00:00'))
    from {{ this }}
  )
{% endif %}
