import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = os.getenv("DB_PORT", "5433")
DB_NAME     = os.getenv("DB_NAME", "tiktok_trend")
DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host     = DB_HOST,
            port     = DB_PORT,
            database = DB_NAME,
            user     = DB_USER,
            password = DB_PASSWORD
        )
        return conn
    except Exception as e:
        print(f"[!] Error connecting to Database: {e}")
        raise
