from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

IMAGE_NAME   = "tiktok-trend-pipeline:latest"
NETWORK_NAME = "docker_default"
PROJECT_DIR  = "/Users/hoanghaianh/DE-TikTokTrend"

MOUNTS = [
    Mount(
        source = f"{PROJECT_DIR}/data",
        target = "/app/data",
        type   = "bind"
    ),
    Mount(
        source = f"{PROJECT_DIR}/.env",
        target = "/app/.env",
        type   = "bind"
    ),
    Mount(
        source = f"{PROJECT_DIR}/dbt_project",
        target = "/app/dbt_project",
        type   = "bind"
    ),
]

default_args = {
    "owner"           : "data_engineer",
    "depends_on_past" : False,
    "start_date"      : datetime(2026, 6, 5),
    "email_on_failure": False,
    "email_on_retry"  : False,
    "retries"         : 2,
    "retry_delay"     : timedelta(minutes=5),
}

with DAG(
    dag_id            = "tiktok_trend_daily_pipeline",
    description       = "Daily pipeline: Crawl TikTok Top Ads → Load to Postgres → dbt Transform",
    default_args      = default_args,
    schedule_interval = "0 8 * * *",
    catchup           = False,
    max_active_runs   = 1,
    tags              = ["tiktok", "data-engineering", "daily"],
) as dag:

    crawl_task = DockerOperator(
        task_id       = "crawl_tiktok_top_ads",
        image         = IMAGE_NAME,
        command       = "python src/crawl_creative_center.py --period 30 --countries VN,US,GB,CA,AU,NZ,SG,MY,PH,ID,HK,TW,TH",
        network_mode  = NETWORK_NAME,
        mounts        = MOUNTS,
        auto_remove   = "success",
        docker_url    = "unix://var/run/docker.sock",
        mount_tmp_dir = False,
        environment   = {
            "DB_HOST"              : "postgres",
            "DB_PORT"              : "5432",
            "DB_NAME"              : "tiktok_trend",
            "DB_USER"              : "postgres",
            "DB_PASSWORD"          : "postgres",
            "S3_ENDPOINT_URL"      : "http://minio:9000",
            "AWS_ACCESS_KEY_ID"    : "minioadmin",
            "AWS_SECRET_ACCESS_KEY": "minioadmin",
            "AWS_REGION"           : "us-east-1",
            "S3_BUCKET_NAME"       : "tiktok-trend-raw",
            "PYTHONPATH"           : "/app",
        }
    )

    load_task = DockerOperator(
        task_id       = "load_to_postgres_staging",
        image         = IMAGE_NAME,
        command       = "python src/load.py",
        network_mode  = NETWORK_NAME,
        mounts        = MOUNTS,
        auto_remove   = "success",
        docker_url    = "unix://var/run/docker.sock",
        mount_tmp_dir = False,
        environment   = {
            "DB_HOST"          : "postgres",
            "DB_PORT"          : "5432",
            "DB_NAME"          : "tiktok_trend",
            "DB_USER"          : "postgres",
            "DB_PASSWORD"      : "postgres",
            "S3_ENDPOINT_URL"  : "http://minio:9000",
            "AWS_ACCESS_KEY_ID": "minioadmin",
            "AWS_SECRET_ACCESS_KEY": "minioadmin",
            "AWS_REGION"       : "us-east-1",
            "S3_BUCKET_NAME"   : "tiktok-trend-raw",
            "PYTHONPATH"       : "/app",
        }
    )

    dbt_task = DockerOperator(
        task_id       = "dbt_transform",
        image         = IMAGE_NAME,
        command       = "dbt run --project-dir dbt_project --profiles-dir dbt_project",
        network_mode  = NETWORK_NAME,
        mounts        = MOUNTS,
        auto_remove   = "success",
        docker_url    = "unix://var/run/docker.sock",
        mount_tmp_dir = False,
        environment   = {
            "DB_HOST"    : "postgres",
            "DB_PORT"    : "5432",
            "DB_NAME"    : "tiktok_trend",
            "DB_USER"    : "postgres",
            "DB_PASSWORD": "postgres",
            "PYTHONPATH" : "/app",
        }
    )

    crawl_task >> load_task >> dbt_task
