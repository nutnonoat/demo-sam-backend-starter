"""Backend Lambda — CRUDQ API for items stored in RDS PostgreSQL."""

import json
import os
import urllib.request
import psycopg2
from contextlib import contextmanager

RDS_SECRET_ARN = os.environ["RDS_SECRET_ARN"]

# ── Secrets Manager (via Lambda Extension) ──
_db_config_cache = None


def _get_db_config():
    global _db_config_cache
    if _db_config_cache is None:
        endpoint = f"http://localhost:2773/secretsmanager/get?secretId={RDS_SECRET_ARN}"
        headers = {"X-Aws-Parameters-Secrets-Token": os.environ.get("AWS_SESSION_TOKEN", "")}
        req = urllib.request.Request(endpoint, headers=headers)
        with urllib.request.urlopen(req) as resp:
            secret = json.loads(json.loads(resp.read())["SecretString"])
        _db_config_cache = {
            "host": secret["host"],
            "port": secret.get("port", 5432),
            "dbname": secret["dbname"],
            "user": secret["username"],
            "password": secret["password"],
        }
    return _db_config_cache


@contextmanager
def get_connection():
    cfg = _get_db_config()
    conn = psycopg2.connect(**cfg)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Helpers ──
def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Access-Control-Allow-Origin": os.environ.get("CORS_ALLOW_ORIGIN", ""),
            "Access-Control-Allow-Headers": "Authorization,Content-Type",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
        },
        "body": json.dumps(body),
    }


def _get_schema():
    project = os.environ.get("PROJECT", "app")
    env = os.environ.get("ENVIRONMENT", "dev")
    return f"{project}_{env}".replace("-", "_")


def _init_table(conn):
    schema = _get_schema()
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name = %s", (schema,))
        if not cur.fetchone():
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        cur.execute(f"SET search_path TO {schema}")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


# ── Route handlers ──
def list_items(conn, params):
    with conn.cursor() as cur:
        limit = int(params.get("limit", 50))
        offset = int(params.get("offset", 0))
        cur.execute("SELECT id, name, description, created_at FROM items ORDER BY id LIMIT %s OFFSET %s", (limit, offset))
        rows = cur.fetchall()
    return _response(200, [{"id": r[0], "name": r[1], "description": r[2], "created_at": str(r[3])} for r in rows])


def get_item(conn, item_id):
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, description, created_at FROM items WHERE id = %s", (item_id,))
        row = cur.fetchone()
    if not row:
        return _response(404, {"error": "Item not found"})
    return _response(200, {"id": row[0], "name": row[1], "description": row[2], "created_at": str(row[3])})


def create_item(conn, body):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO items (name, description) VALUES (%s, %s) RETURNING id, name, description, created_at",
            (body["name"], body.get("description", "")),
        )
        row = cur.fetchone()
    return _response(201, {"id": row[0], "name": row[1], "description": row[2], "created_at": str(row[3])})


def update_item(conn, item_id, body):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE items SET name = %s, description = %s WHERE id = %s RETURNING id, name, description, created_at",
            (body["name"], body.get("description", ""), item_id),
        )
        row = cur.fetchone()
    if not row:
        return _response(404, {"error": "Item not found"})
    return _response(200, {"id": row[0], "name": row[1], "description": row[2], "created_at": str(row[3])})


def delete_item(conn, item_id):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM items WHERE id = %s RETURNING id", (item_id,))
        row = cur.fetchone()
    if not row:
        return _response(404, {"error": "Item not found"})
    return _response(200, {"message": f"Item {item_id} deleted"})


# ── Lambda handler ──
def handler(event, context):
    method = event.get("httpMethod", "")
    path = event.get("path", "")
    path_params = event.get("pathParameters") or {}
    query_params = event.get("queryStringParameters") or {}

    try:
        with get_connection() as conn:
            _init_table(conn)

            if path == "/items" and method == "GET":
                return list_items(conn, query_params)
            elif path.startswith("/items/") and method == "GET":
                return get_item(conn, path_params["id"])
            elif path == "/items" and method == "POST":
                body = json.loads(event.get("body", "{}"))
                return create_item(conn, body)
            elif path.startswith("/items/") and method == "PUT":
                body = json.loads(event.get("body", "{}"))
                return update_item(conn, path_params["id"], body)
            elif path.startswith("/items/") and method == "DELETE":
                return delete_item(conn, path_params["id"])
            else:
                return _response(404, {"error": "Route not found"})
    except Exception as e:
        return _response(500, {"error": str(e)})
