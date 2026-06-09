import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from config import (
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,
    DB_ADMIN_USER, DB_ADMIN_PASSWORD,
)


def ensure_ready() -> None:
    """Crea la base de datos y el usuario si no existen, luego inicializa las tablas."""
    _create_db_and_user()
    import db
    db.init_schema()


def _create_db_and_user() -> None:
    # Conectamos al DB por defecto 'postgres' como superusuario
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname="postgres",
        user=DB_ADMIN_USER,
        password=DB_ADMIN_PASSWORD,
    )
    # CREATE DATABASE no puede correr dentro de una transacción
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

    try:
        with conn.cursor() as cur:
            # Crear usuario si no existe
            cur.execute(
                "SELECT 1 FROM pg_roles WHERE rolname = %s", (DB_USER,)
            )
            if not cur.fetchone():
                cur.execute(
                    sql.SQL("CREATE USER {} WITH PASSWORD %s").format(
                        sql.Identifier(DB_USER)
                    ),
                    (DB_PASSWORD,),
                )
                print(f"[Setup] Usuario '{DB_USER}' creado")
            else:
                print(f"[Setup] Usuario '{DB_USER}' ya existe")

            # Crear base de datos si no existe
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,)
            )
            if not cur.fetchone():
                cur.execute(
                    sql.SQL("CREATE DATABASE {} OWNER {}").format(
                        sql.Identifier(DB_NAME),
                        sql.Identifier(DB_USER),
                    )
                )
                print(f"[Setup] Base de datos '{DB_NAME}' creada")
            else:
                print(f"[Setup] Base de datos '{DB_NAME}' ya existe")

            # Garantizar privilegios
            cur.execute(
                sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                    sql.Identifier(DB_NAME),
                    sql.Identifier(DB_USER),
                )
            )
    finally:
        conn.close()


if __name__ == "__main__":
    ensure_ready()
    print("[Setup] Todo listo.")
