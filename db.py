import psycopg2
import psycopg2.pool
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

_pool: psycopg2.pool.SimpleConnectionPool | None = None


def get_pool() -> psycopg2.pool.SimpleConnectionPool:
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.SimpleConnectionPool(
            1, 5,
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
    return _pool


def init_schema() -> None:
    pool = get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id               SERIAL PRIMARY KEY,
                    event_id         UUID UNIQUE NOT NULL,
                    captured_at      TIMESTAMPTZ NOT NULL,
                    hour_of_day      SMALLINT NOT NULL,
                    motion_detected  BOOLEAN NOT NULL,
                    motion_confidence FLOAT NOT NULL,
                    face_detected    BOOLEAN NOT NULL,
                    light_percent    FLOAT NOT NULL,
                    alert_level      TEXT NOT NULL,
                    anomaly_score    FLOAT NOT NULL,
                    rapiro_command   TEXT NOT NULL,
                    mqtt_published   BOOLEAN NOT NULL DEFAULT false
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS hourly_patterns (
                    hour_of_day       SMALLINT PRIMARY KEY,
                    avg_motion_freq   FLOAT NOT NULL DEFAULT 0,
                    avg_light_percent FLOAT NOT NULL DEFAULT 0,
                    motion_std        FLOAT NOT NULL DEFAULT 0.1,
                    light_std         FLOAT NOT NULL DEFAULT 0.05,
                    sample_count      INTEGER NOT NULL DEFAULT 0,
                    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        conn.commit()
        print("[DB] Schema inicializado")
    finally:
        pool.putconn(conn)


def save_event(event: dict) -> int:
    pool = get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO events (
                    event_id, captured_at, hour_of_day,
                    motion_detected, motion_confidence, face_detected,
                    light_percent, alert_level, anomaly_score, rapiro_command
                ) VALUES (
                    %(event_id)s, %(captured_at)s, %(hour_of_day)s,
                    %(motion_detected)s, %(motion_confidence)s, %(face_detected)s,
                    %(light_percent)s, %(alert_level)s, %(anomaly_score)s, %(rapiro_command)s
                ) RETURNING id
            """, event)
            row_id = cur.fetchone()[0]
        conn.commit()
        return row_id
    finally:
        pool.putconn(conn)


def mark_mqtt_published(row_id: int) -> None:
    pool = get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE events SET mqtt_published = true WHERE id = %s",
                (row_id,)
            )
        conn.commit()
    finally:
        pool.putconn(conn)


def close_pool() -> None:
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None
