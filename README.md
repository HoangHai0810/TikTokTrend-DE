# TikTok Trend — Data Engineering Pipeline

An end-to-end data engineering project that automatically crawls TikTok Creative Center's Top Ads, stores raw data in cloud object storage, transforms it into an analytics-ready data warehouse, and serves insights via a custom interactive dashboard.

---

## 🏗️ Architecture

```
TikTok Creative Center
        │
        ▼ Playwright (Browser Automation + API Interception)
src/crawl_creative_center.py
        │
        ▼ boto3 (S3-compatible)
MinIO / AWS S3  ──── raw JSON per day
        │
        ▼ psycopg2 UPSERT
PostgreSQL → public.stg_tiktok_topads  (raw staging)
        │
        ▼ dbt run
public_staging.stg_topads              (VIEW — cleaned, typed)
        │
        ├── public_analytics.dim_ads            (Dimension Table)
        └── public_analytics.fact_ad_performance (Fact Table)
                │
                ▼ Streamlit + Plotly
        src/dashboard.py  →  http://localhost:8501

Apache Airflow  ─── orchestrates all steps daily at 08:00 AM
```

---

## 📁 Project Structure

```
DE-TikTokTrend/
├── dags/
│   └── tiktok_trend_dag.py      # Airflow DAG: crawl → load → dbt
├── data/
│   ├── raw/                     # Local raw JSON snapshots (gitignored)
│   └── tiktok_filters.json      # Official TikTok Creative Center filter metadata
├── dbt_project/
│   ├── models/
│   │   ├── staging/             # stg_topads view: cast types, extract JSON fields
│   │   └── marts/               # dim_ads, fact_ad_performance tables
│   ├── dbt_project.yml
│   └── profiles.yml
├── docker/
│   └── docker-compose.yml       # PostgreSQL + MinIO + Airflow services
├── queries/
│   └── trend_detection.sql      # EDA queries: hashtag analysis, growth rate, leaderboard
├── scripts/
│   ├── run_pipeline.sh          # Manual full pipeline run
│   └── run_dashboard.sh         # Launch Streamlit dashboard
├── src/
│   ├── crawl_creative_center.py # Playwright crawler with multi-page collection
│   ├── load.py                  # Load raw JSON → Postgres staging
│   ├── dashboard.py             # Streamlit analytics dashboard
│   └── utils/
│       ├── db.py                # Postgres connection helper
│       └── s3.py                # MinIO/S3 upload & download helpers
├── Dockerfile                   # Pipeline image: Python 3.11 + Playwright + dbt
├── requirements.txt
└── .env                         # Environment variables (gitignored)
```

---

## 🚀 Quick Start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (≥ 4.x)
- Python 3.11+ with `venv`
- Git

### 1. Clone & Configure

```bash
git clone https://github.com/HoangHai0810/TikTokTrend-DE.git
cd TikTokTrend-DE

# Copy and edit environment variables
cp .env.example .env
```

**`.env` configuration:**

```ini
# PostgreSQL
DB_HOST=localhost
DB_PORT=5433
DB_NAME=tiktok_trend
DB_USER=postgres
DB_PASSWORD=postgres

# MinIO (local S3 emulator) — or use real AWS S3 credentials
S3_ENDPOINT_URL=http://localhost:9000
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
AWS_REGION=us-east-1
S3_BUCKET_NAME=tiktok-trend-raw
```

> **To use AWS S3 instead of MinIO:** Remove `S3_ENDPOINT_URL` and replace the key/secret with real AWS credentials.

### 2. Start Infrastructure

```bash
docker compose -f docker/docker-compose.yml up -d
```

This starts:
| Service | Port | Purpose |
|---------|------|---------|
| PostgreSQL | 5433 | Data Warehouse |
| MinIO | 9000 / 9001 | S3-compatible Object Storage |
| Airflow Webserver | 8080 | Pipeline Scheduler UI |
| Airflow Scheduler | — | Background DAG runner |

### 3. Set Up Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install streamlit plotly

# Install Playwright's Chromium browser
playwright install chromium
```

### 4. Build the Pipeline Docker Image

The Airflow DAG runs each step inside a Docker container using this image:

```bash
docker build -t tiktok-trend-pipeline:latest .
```

### 5. Create MinIO Bucket

Open MinIO Console at [http://localhost:9001](http://localhost:9001) (user: `minioadmin`, password: `minioadmin`) and create a bucket named `tiktok-trend-raw`.

---

## 🔄 Running the Pipeline

### Option A — Manual Run (One-Shot)

```bash
./scripts/run_pipeline.sh
```

By default the pipeline crawls `VN,US,GB,CA,AU,NZ,SG,MY,PH,ID,HK,TW,TH`. To change the country set, edit the `--countries` list in `scripts/run_pipeline.sh` or the Airflow DAG command.

This executes all three steps in sequence:
1. **Crawl** — Intercepts TikTok Creative Center API responses and collects Top Ads across multiple pages and countries
2. **Load** — Reads raw JSON from MinIO, upserts into `public.stg_tiktok_topads`
3. **Transform** — Runs `dbt run` to populate the `dim_ads` and `fact_ad_performance` tables

### Option B — Automated Daily Schedule (Airflow)

The DAG `tiktok_trend_daily_pipeline` is pre-configured to run daily at **08:00 AM**.

1. Open Airflow UI: [http://localhost:8080](http://localhost:8080) (user: `admin`, password: `admin`)
2. Find `tiktok_trend_daily_pipeline` and toggle it **On**
3. Click **▶ Trigger DAG** to run immediately

---

## 📊 Analytics Dashboard

```bash
./scripts/run_dashboard.sh
```

Open [http://localhost:8501](http://localhost:8501) to access the dashboard.

### Features

| Tab | Description |
|-----|-------------|
| **🏆 Top Ads Leaderboard** | Ranked table with cover images, likes, CTR, and direct video links |
| **📈 Trend & Growth** | Interactive Plotly charts showing cumulative likes and average CTR over time |
| **🏷️ Industry & Hashtags** | Bar charts of top-10 industries and top-15 trending hashtags (auto-extracted from ad titles) |
| **📽️ Video Player & Deep Dive** | Select any ad to play its video inline, view metadata, and see its historical engagement trend |

**Sidebar filters:** Crawl date, country, industry, CTR range, minimum likes, and free-text search.

> Industry and campaign objective names are loaded dynamically from `data/tiktok_filters.json` — the official TikTok Creative Center filter metadata — so labels are always accurate and never hardcoded.

---

## 🗄️ Data Model

### Layers

| Schema | Table / View | Type | Description |
|--------|-------------|------|-------------|
| `public` | `stg_tiktok_topads` | Table | Raw JSON data ingested from MinIO/S3. Contains `video_info` as JSONB and `country_code` for multi-country analysis. |
| `public_staging` | `stg_topads` | View (dbt) | Typed and renamed fields. Extracts `video_url_1080p`, `video_duration`, etc. from JSONB. |
| `public_analytics` | `dim_ads` | Table (dbt) | **Dimension table.** Unique ad-country records, de-duplicated to the latest crawl. |
| `public_analytics` | `fact_ad_performance` | Table (dbt) | **Fact table.** Daily performance metrics (likes, CTR, cost level) per ad and country. |

> **The cleanest data for analysis lives in `public_analytics`.**

### Key Columns

**`dim_ads`**
| Column | Description |
|--------|-------------|
| `ad_id` | Unique TikTok ad identifier |
| `country_code` | Country/nation where the ad was captured |
| `ad_title` | Ad copy / title text (may contain hashtags) |
| `brand_name` | Advertiser brand |
| `industry_key` | TikTok industry category label |
| `objective_key` | Campaign objective (Video Views, Conversions, etc.) |
| `video_url_1080p` | Direct video stream URL (1080p) |
| `video_cover_url` | Cover image URL |

**`fact_ad_performance`**
| Column | Description |
|--------|-------------|
| `ad_performance_key` | Surrogate key (MD5 of ad_id + crawled_date + country_code) |
| `country_code` | Country/nation where the ad was captured |
| `crawled_date` | Date the ad was captured |
| `like_count` | Total likes at time of crawl |
| `ctr_rate` | Click-through rate |
| `cost_level` | Relative ad spend indicator |
| `is_search` | Whether the ad appeared in search placements |

---

## 🛠️ Key Technologies

| Tool | Role |
|------|------|
| **Python 3.11** | Core scripting language |
| **Playwright** | Headless browser for API interception |
| **PostgreSQL 15** | Data warehouse |
| **dbt-postgres** | SQL transformations and data modelling |
| **Apache Airflow 2.9** | Pipeline orchestration and scheduling |
| **MinIO** | Local S3-compatible object storage for raw files |
| **boto3** | AWS S3 / MinIO SDK for upload & download |
| **Streamlit** | Interactive analytics dashboard |
| **Plotly** | Interactive charts and visualizations |
| **Docker & Docker Compose** | Service containerisation |

---

## 📝 Useful Queries

Pre-written analytical queries are available in [`queries/trend_detection.sql`](queries/trend_detection.sql):

- **Hashtag popularity & engagement** — Frequency and average CTR per hashtag
- **Industry leaderboard** — Which verticals dominate by ad count and total likes
- **Day-over-day growth** — `LAG()` window function to track like velocity per ad

---

## ⚙️ Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | Postgres host |
| `DB_PORT` | `5433` | Postgres port |
| `DB_NAME` | `tiktok_trend` | Postgres database name |
| `DB_USER` | `postgres` | Postgres username |
| `DB_PASSWORD` | `postgres` | Postgres password |
| `S3_ENDPOINT_URL` | `http://localhost:9000` | MinIO endpoint (remove for real AWS S3) |
| `AWS_ACCESS_KEY_ID` | `minioadmin` | S3 access key |
| `AWS_SECRET_ACCESS_KEY` | `minioadmin` | S3 secret key |
| `AWS_REGION` | `us-east-1` | S3 region |
| `S3_BUCKET_NAME` | `tiktok-trend-raw` | S3 bucket for raw JSON files |
