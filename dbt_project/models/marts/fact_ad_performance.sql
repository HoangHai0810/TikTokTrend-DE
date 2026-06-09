with staging as (
    select * from {{ ref('stg_topads') }}
)

select
    -- Surrogate key theo ad, ngày crawl và quốc gia để không ghi đè khi crawl nhiều nước.
    md5(concat(ad_id, '_', cast(crawled_date as varchar), '_', country_code)) as ad_performance_key,
    ad_id,
    country_code,
    crawled_date,
    cost_level,
    ctr_rate,
    is_favorite,
    is_search,
    like_count,
    period_days,
    crawled_at
from staging
