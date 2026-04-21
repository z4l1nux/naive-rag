import contextlib
import os
from typing import Generator

import psycopg2
import psycopg2.pool
import psycopg2.extras

_pool: psycopg2.pool.ThreadedConnectionPool | None = None

EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))

# HNSW supports up to 2000 dims for vector, up to 4000 dims for halfvec.
# Values come from a binary choice over a validated integer — never user input.
_use_halfvec = EMBEDDING_DIM > 2000
_col_type  = f"halfvec({EMBEDDING_DIM})" if _use_halfvec else f"vector({EMBEDDING_DIM})"
_cast_type = "halfvec" if _use_halfvec else "vector"
_ops_class = "halfvec_cosine_ops" if _use_halfvec else "vector_cosine_ops"

# SQL templates built once at module load — interpolation happens here, not inside execute().
# DDL type names (vector/halfvec) cannot be parameterised in PostgreSQL; the values
# are derived from _use_halfvec (binary flag) and EMBEDDING_DIM (integer), not from input.
_SQL_CREATE_TABLE = f"""
    CREATE TABLE IF NOT EXISTS documents (
        id          SERIAL PRIMARY KEY,
        content     TEXT NOT NULL,
        embedding   {_col_type},
        source_file TEXT,
        chunk_index INTEGER,
        created_at  TIMESTAMPTZ DEFAULT NOW()
    )"""

_SQL_CREATE_INDEX = f"""
    CREATE INDEX IF NOT EXISTS documents_embedding_hnsw_idx
    ON documents USING hnsw (embedding {_ops_class})"""

_SQL_INSERT = f"""
    INSERT INTO documents (content, embedding, source_file, chunk_index)
    VALUES (%s, %s::{_cast_type}, %s, %s)
    RETURNING id, content, source_file, chunk_index, created_at"""

_SQL_FIND_SIMILAR = f"""
    SELECT id, content, source_file,
           ROUND((1 - (embedding <=> %s::{_cast_type}))::numeric, 4) AS similarity
    FROM documents
    ORDER BY embedding <=> %s::{_cast_type}
    LIMIT %s"""


def init_db() -> None:
    dsn = os.getenv("DATABASE_URL")

    # Use a temporary connection with autocommit for DDL
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

    cur.execute(_SQL_CREATE_TABLE)   # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query,python.lang.security.audit.formatted-sql-query.formatted-sql-query,python.lang.security.audit.sqli.psycopg-sqli.psycopg-sqli
    # Non-destructive migration for tables created before file upload support
    cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_file TEXT")
    cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS chunk_index INTEGER")

    cur.execute(_SQL_CREATE_INDEX)   # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query,python.lang.security.audit.formatted-sql-query.formatted-sql-query,python.lang.security.audit.sqli.psycopg-sqli.psycopg-sqli

    cur.close()
    conn.close()

    global _pool
    _pool = psycopg2.pool.ThreadedConnectionPool(minconn=1, maxconn=5, dsn=dsn)


@contextlib.contextmanager
def get_db() -> Generator[psycopg2.extensions.connection, None, None]:
    assert _pool is not None, "Database not initialised — call init_db() first"
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


# ── Types ────────────────────────────────────────────────────────────

def _vec(embedding: list[float]) -> str:
    """Format a float list as a pgvector literal: [1.1,2.2,...]"""
    return f"[{','.join(str(x) for x in embedding)}]"


# ── Queries ──────────────────────────────────────────────────────────

def insert_document(
    content: str,
    embedding: list[float],
    source_file: str | None = None,
    chunk_index: int | None = None,
) -> dict:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(_SQL_INSERT, (content, _vec(embedding), source_file, chunk_index))  # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        return dict(cur.fetchone())


def list_documents() -> list[dict]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT id, content, source_file, chunk_index, created_at
            FROM documents
            WHERE source_file IS NULL
            ORDER BY created_at DESC
            """
        )
        return [dict(row) for row in cur.fetchall()]


def list_files() -> list[dict]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT source_file,
                   COUNT(*)::int  AS chunk_count,
                   MAX(created_at) AS created_at
            FROM documents
            WHERE source_file IS NOT NULL
            GROUP BY source_file
            ORDER BY MAX(created_at) DESC
            """
        )
        return [dict(row) for row in cur.fetchall()]


def delete_document(doc_id: int) -> bool:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
        return cur.rowcount > 0


def delete_file(source_file: str) -> int:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM documents WHERE source_file = %s", (source_file,))
        return cur.rowcount


def find_similar(embedding: list[float], top_k: int) -> list[dict]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(_SQL_FIND_SIMILAR, (_vec(embedding), _vec(embedding), top_k))  # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        return [dict(row) for row in cur.fetchall()]
