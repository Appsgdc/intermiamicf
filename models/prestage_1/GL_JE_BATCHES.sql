select *
from `useful-lattice-472005-i4.hr_demo.GL_JE_BATCHES`
{% if is_incremental() %}
  where LASTUPDATEDATE >= (
    select coalesce(max(LASTUPDATEDATE), timestamp('1900-01-01 00:00:00'))
    from {{ this }}
  )
{% endif %}
