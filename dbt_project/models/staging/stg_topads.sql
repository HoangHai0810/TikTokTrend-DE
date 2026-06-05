with source as (
    select * from {{ source('public', 'stg_tiktok_topads') }}
),

renamed as (
    select
        id as ad_id,
        crawled_date,
        ad_title,
        brand_name,
        cost as cost_level,
        ctr as ctr_rate,
        favorite as is_favorite,
        industry_key,
        is_search,
        like_count,
        objective_key,
        country_code,
        period as period_days,
        crawled_at,
        loaded_at,
        
        video_info->>'vid' as video_id,
        cast(video_info->>'duration' as double precision) as video_duration,
        video_info->>'cover' as video_cover_url,
        cast(video_info->>'width' as integer) as video_width,
        cast(video_info->>'height' as integer) as video_height,
        video_info->'video_url'->>'1080p' as video_url_1080p,
        video_info->'video_url'->>'720p' as video_url_720p
    from source
)

select * from renamed
