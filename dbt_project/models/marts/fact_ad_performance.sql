with staging as (
    select * from {{ ref('stg_topads') }}
)

select
    -- Tạo Surrogate Key làm khóa chính cho bảng fact dựa trên ad_id và ngày crawl
    md5(concat(ad_id, '_', cast(crawled_date as varchar))) as ad_performance_key,
    ad_id,
    crawled_date,
    cost_level,
    ctr_rate,
    is_favorite,
    is_search,
    like_count,
    period_days,
    crawled_at
from staging
