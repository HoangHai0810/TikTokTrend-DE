with staging as (
    select * from {{ ref('stg_topads') }}
),

ranked as (
    select
        ad_id,
        ad_title,
        brand_name,
        industry_key,
        objective_key,
        country_code,
        video_id,
        video_duration,
        video_cover_url,
        video_width,
        video_height,
        video_url_1080p,
        video_url_720p,
        crawled_at,
        row_number() over (partition by ad_id order by crawled_at desc) as rn
    from staging
)

select
    ad_id,
    ad_title,
    brand_name,
    industry_key,
    objective_key,
    country_code,
    video_id,
    video_duration,
    video_cover_url,
    video_width,
    video_height,
    video_url_1080p,
    video_url_720p,
    crawled_at as last_seen_at
from ranked
where rn = 1
