import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    """
    Tạo và trả về connection kết nối đến PostgreSQL 16.
    """
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME", "GarenaShop_DB"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "qtdl1234")
        )
        return conn
    except Exception as e:
        print(f"❌ Lỗi kết nối CSDL: {e}")
        raise e
