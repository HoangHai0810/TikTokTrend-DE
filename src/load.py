import os
import json
import argparse
import sys
from datetime import datetime
import psycopg2
from psycopg2.extras import Json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.db import get_db_connection


def parse_country_codes(country_arg: str | None, countries_arg: str | None) -> list[str]:
    raw_codes = countries_arg or country_arg
    if not raw_codes:
        return []
    countries = []
    for code in raw_codes.split(","):
        normalized = code.strip().upper()
        if normalized and normalized not in countries:
            countries.append(normalized)
    return countries


def create_staging_table(conn):
    create_sql = """
    CREATE TABLE IF NOT EXISTS stg_tiktok_topads (
        id VARCHAR(50),
        crawled_date DATE,
        ad_title TEXT,
        brand_name TEXT,
        cost INT,
        ctr DOUBLE PRECISION,
        favorite BOOLEAN,
        industry_key VARCHAR(100),
        is_search BOOLEAN,
        like_count INT,
        objective_key VARCHAR(100),
        video_info JSONB,
        country_code VARCHAR(10),
        period INT,
        crawled_at TIMESTAMP WITH TIME ZONE,
        loaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id, crawled_date, country_code)
    );
    """
    with conn.cursor() as cur:
        cur.execute(create_sql)
    conn.commit()
    ensure_staging_primary_key(conn)
    print("[INFO] `stg_tiktok_topads` table is ready.")


def ensure_staging_primary_key(conn):
    expected_columns = ["id", "crawled_date", "country_code"]
    with conn.cursor() as cur:
        cur.execute("""
            SELECT c.conname, array_agg(a.attname ORDER BY k.ordinality) AS columns
            FROM pg_constraint c
            JOIN unnest(c.conkey) WITH ORDINALITY AS k(attnum, ordinality) ON true
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
            WHERE c.conrelid = 'stg_tiktok_topads'::regclass
              AND c.contype = 'p'
            GROUP BY c.conname;
        """)
        row = cur.fetchone()
        if row and list(row[1]) == expected_columns:
            conn.commit()
            return

        cur.execute("""
            UPDATE stg_tiktok_topads
            SET country_code = 'UNKNOWN'
            WHERE country_code IS NULL;
        """)
        if row:
            cur.execute(f'ALTER TABLE stg_tiktok_topads DROP CONSTRAINT "{row[0]}";')
        cur.execute("""
            ALTER TABLE stg_tiktok_topads
            ADD PRIMARY KEY (id, crawled_date, country_code);
        """)
    conn.commit()
    print("[INFO] Primary key is now `(id, crawled_date, country_code)`.")


def read_raw_json(date_str: str, country_code: str | None = None):
    suffix = f"_{country_code}" if country_code else ""
    s3_key = f"tiktok_creative_center/{date_str}/raw_topads_{date_str}{suffix}.json"

    # Thử đọc từ Cloud Storage (S3/MinIO) trước
    try:
        from src.utils.s3 import read_json_from_s3
        print(f"[INFO] Đang tìm kiếm và đọc dữ liệu thô từ S3: s3://tiktok-trend-raw/{s3_key}")
        raw_data = read_json_from_s3(s3_key)
        print("[SUCCESS] Đọc dữ liệu thành công từ S3/MinIO.")
        return raw_data
    except Exception as s3_err:
        print(f"[WARNING] Không thể đọc từ S3/MinIO: {s3_err}")
        
        # Fallback: Đọc từ file cục bộ (local disk)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(
            current_dir, 
            f"../data/raw/tiktok_creative_center/{date_str}/raw_topads_{date_str}{suffix}.json"
        )
        file_path = os.path.abspath(file_path)

        if not os.path.exists(file_path):
            print(f"[ERROR] Cả S3 và file cục bộ đều không tồn tại tại: {file_path}")
            return None

        print(f"[INFO] Fallback: Đang đọc file cục bộ tại {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)


def iter_country_payloads(raw_data: dict):
    country_results = raw_data.get("country_results")
    if country_results:
        yield from country_results
    else:
        yield raw_data


def extract_ads_from_payload(raw_data: dict, date_str: str):
    crawled_at_str = raw_data.get("crawled_at")
    period         = raw_data.get("period")
    country_code   = raw_data.get("country_code")

    if not crawled_at_str:
        print("[ERROR] `crawled_at` field not found in JSON.")
        return []

    try:
        crawled_at_dt = datetime.strptime(crawled_at_str, "%Y-%m-%d %H:%M:%S")
        crawled_date  = crawled_at_dt.date()
    except Exception as e:
        print(f"[ERROR] Error parsing crawled_at: {e}")
        crawled_date  = datetime.strptime(date_str, "%Y-%m-%d").date()
        crawled_at_dt = datetime.now()

    top_ads_list = raw_data.get("top_ads_list")
    if not top_ads_list or "data" not in top_ads_list:
        print("[ERROR] No top_ads_list data found in JSON.")
        return []

    materials = top_ads_list["data"].get("materials", [])
    if not materials:
        print("[WARNING] `materials` list is empty.")
        return []

    rows = []
    for ad in materials:
        ad_country_code = (ad.get("country_code") or country_code or "UNKNOWN").upper()
        rows.append((ad, ad_country_code, period, crawled_date, crawled_at_dt))
    return rows


def load_raw_to_staging(date_str: str, countries: list[str] | None = None):
    raw_payloads = []
    for country_code in countries or [None]:
        raw_data = read_raw_json(date_str, country_code)
        if raw_data:
            raw_payloads.extend(iter_country_payloads(raw_data))

    if not raw_payloads:
        print("[ERROR] No raw payloads found to load.")
        return

    rows = []
    for payload in raw_payloads:
        rows.extend(extract_ads_from_payload(payload, date_str))

    if not rows:
        print("[ERROR] No ads found in raw payloads.")
        return

    print(f"[INFO] Starting to load {len(rows)} ads into Postgres...")
    conn = get_db_connection()
    
    try:
        create_staging_table(conn)

        upsert_sql = """
        INSERT INTO stg_tiktok_topads (
            id, crawled_date, ad_title, brand_name, cost, ctr, 
            favorite, industry_key, is_search, like_count, 
            objective_key, video_info, country_code, period, crawled_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, 
            %s, %s, %s, %s, 
            %s, %s, %s, %s, %s
        )
        ON CONFLICT (id, crawled_date, country_code)
        DO UPDATE SET
            ad_title = EXCLUDED.ad_title,
            brand_name = EXCLUDED.brand_name,
            cost = EXCLUDED.cost,
            ctr = EXCLUDED.ctr,
            favorite = EXCLUDED.favorite,
            industry_key = EXCLUDED.industry_key,
            is_search = EXCLUDED.is_search,
            like_count = EXCLUDED.like_count,
            objective_key = EXCLUDED.objective_key,
            video_info = EXCLUDED.video_info,
            country_code = EXCLUDED.country_code,
            period = EXCLUDED.period,
            crawled_at = EXCLUDED.crawled_at,
            loaded_at = CURRENT_TIMESTAMP;
        """

        success_count = 0
        with conn.cursor() as cur:
            for ad, country_code, period, crawled_date, crawled_at_dt in rows:
                ad_id = ad.get("id")
                if not ad_id:
                    continue

                ad_title        = ad.get("ad_title")
                brand_name      = ad.get("brand_name")
                cost            = ad.get("cost")
                ctr             = ad.get("ctr")
                favorite        = ad.get("favorite")
                industry_key    = ad.get("industry_key")
                is_search       = ad.get("is_search")
                like_count      = ad.get("like")
                objective_key   = ad.get("objective_key")
                video_info      = ad.get("video_info")
                video_info_json = Json(video_info) if video_info else None

                cur.execute(upsert_sql, (
                    str(ad_id),
                    crawled_date,
                    ad_title,
                    brand_name,
                    cost,
                    ctr,
                    favorite,
                    industry_key,
                    is_search,
                    like_count,
                    objective_key,
                    video_info_json,
                    country_code,
                    period,
                    crawled_at_dt
                ))
                success_count += 1

        conn.commit()
        print(f"[SUCCESS] UPSERTED {success_count}/{len(rows)} ads into `stg_tiktok_topads`.")

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Error loading data: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load TikTok raw JSON to PostgreSQL Staging")
    parser.add_argument(
        "--date", 
        type=str, 
        default=datetime.now().strftime("%Y-%m-%d"), 
        help="Date of data to load (YYYY-MM-DD)"
    )
    parser.add_argument("--country", type=str, default=None, help="Country code or comma-separated country codes to load")
    parser.add_argument("--countries", type=str, default=None, help="Comma-separated country codes to load")
    args = parser.parse_args()
    countries = parse_country_codes(args.country, args.countries)
    
    print("=" * 60)
    print(f"ETL Load Step: raw JSON -> Postgres Staging ({args.date})")
    print("=" * 60)
    
    load_raw_to_staging(args.date, countries)
    print("=" * 60)
