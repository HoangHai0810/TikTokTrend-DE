-- =========================================================================
-- QUERIES FOR EDA & TREND DETECTION IN TIKTOK CREATIVE CENTER TOP ADS
-- =========================================================================

-- -------------------------------------------------------------------------
-- QUERY 1: Phân tích Hashtag Phổ biến & Mức độ tương tác (Engagement)
-- -------------------------------------------------------------------------
-- Mục tiêu: Trích xuất tất cả các hashtag từ tiêu đề quảng cáo (ad_title),
-- đếm tần suất xuất hiện và tính CTR trung bình, tổng lượt thích cho mỗi hashtag.

WITH extracted_hashtags AS (
    SELECT 
        ad_id,
        UNNEST(REGEXP_MATCHES(ad_title, '#[a-zA-Z0-9_]+', 'g')) as hashtag
    FROM public_analytics.dim_ads
),

hashtag_performance AS (
    SELECT 
        LOWER(eh.hashtag) as clean_hashtag,
        COUNT(DISTINCT eh.ad_id) as ad_count,
        ROUND(AVG(fp.ctr_rate)::numeric, 4) as avg_ctr,
        SUM(fp.like_count) as total_likes,
        ROUND(AVG(fp.like_count)::numeric, 1) as avg_likes
    FROM extracted_hashtags eh
    JOIN public_analytics.fact_ad_performance fp ON eh.ad_id = fp.ad_id
    GROUP BY clean_hashtag
)

SELECT 
    clean_hashtag,
    ad_count,
    avg_ctr,
    total_likes,
    avg_likes
FROM hashtag_performance
ORDER BY ad_count DESC, total_likes DESC
LIMIT 20;


-- -------------------------------------------------------------------------
-- QUERY 2: Xếp hạng ngành hàng (Industry Leaderboard)
-- -------------------------------------------------------------------------
-- Mục tiêu: Xem ngành hàng nào (industry_key) đang chiếm sóng nhiều nhất,
-- có CTR cao nhất và thu hút nhiều tương tác nhất.

SELECT 
    da.industry_key,
    COUNT(DISTINCT da.ad_id) as total_ads,
    ROUND(AVG(fp.ctr_rate)::numeric, 4) as avg_ctr,
    SUM(fp.like_count) as total_likes,
    ROUND(AVG(fp.like_count)::numeric, 1) as avg_likes
FROM public_analytics.dim_ads da
JOIN public_analytics.fact_ad_performance fp ON da.ad_id = fp.ad_id
GROUP BY da.industry_key
ORDER BY total_ads DESC, avg_ctr DESC;


-- -------------------------------------------------------------------------
-- QUERY 3: Tốc độ tăng trưởng lượt thích theo ngày (Window Function LAG())
-- -------------------------------------------------------------------------
-- Mục tiêu: Theo dõi sự biến động số lượng lượt thích (like_count) của từng 
-- quảng cáo qua từng ngày crawl, tính số lượt thích tăng thêm (diff) và % tăng trưởng.

WITH daily_metrics AS (
    SELECT
        ad_id,
        crawled_date,
        like_count,
        ctr_rate,
        -- Lấy số lượt thích của ngày hôm trước
        LAG(like_count, 1) OVER (
            PARTITION BY ad_id 
            ORDER BY crawled_date ASC
        ) as prev_day_likes
    FROM public_analytics.fact_ad_performance
),

growth_calculation AS (
    SELECT
        ad_id,
        crawled_date,
        like_count as current_likes,
        prev_day_likes,
        (like_count - prev_day_likes) as likes_added,
        CASE 
            WHEN prev_day_likes IS NULL OR prev_day_likes = 0 THEN 0.0
            ELSE ROUND(((like_count - prev_day_likes)::numeric / prev_day_likes) * 100, 2)
        END as growth_percentage
    FROM daily_metrics
)

SELECT 
    da.ad_title,
    da.brand_name,
    gc.crawled_date,
    gc.current_likes,
    gc.prev_day_likes,
    gc.likes_added,
    gc.growth_percentage
FROM growth_calculation gc
JOIN public_analytics.dim_ads da ON gc.ad_id = da.ad_id
ORDER BY gc.likes_added DESC, gc.growth_percentage DESC;
