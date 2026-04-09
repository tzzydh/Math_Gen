import os
import sqlite3
from typing import Optional

from core.auth import hash_password
from core.settings import settings


def get_conn(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or settings.app_db_path
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    columns = {row[1] for row in cur.fetchall()}
    if column not in columns:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_db(db_path: Optional[str] = None) -> None:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS orgs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            plan TEXT NOT NULL DEFAULT 'free',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT,
            password_hash TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(org_id) REFERENCES orgs(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id INTEGER NOT NULL,
            stem TEXT NOT NULL,
            options_json TEXT NOT NULL DEFAULT '[]',
            answer TEXT NOT NULL DEFAULT '',
            analysis TEXT NOT NULL DEFAULT '',
            difficulty TEXT NOT NULL DEFAULT '中',
            chapter TEXT NOT NULL DEFAULT '',
            created_by INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(org_id) REFERENCES orgs(id),
            FOREIGN KEY(created_by) REFERENCES users(id)
        )
        """
    )
    _ensure_column(conn, "users", "password_hash", "password_hash TEXT NOT NULL DEFAULT ''")

    conn.commit()
    conn.close()


def create_org(name: str, plan: str = "free", status: str = "active", db_path: Optional[str] = None) -> int:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO orgs(name, plan, status) VALUES (?, ?, ?)", (name, plan, status))
    conn.commit()
    org_id = cur.lastrowid
    conn.close()
    return org_id


def list_orgs(db_path: Optional[str] = None):
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, name, plan, status, created_at FROM orgs ORDER BY id DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def create_user(org_id: int, role: str, name: str, email: str = "", password: str = "123456", db_path: Optional[str] = None) -> int:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id FROM orgs WHERE id = ?", (org_id,))
    if cur.fetchone() is None:
        conn.close()
        raise ValueError(f"org_id={org_id} 不存在")
    cur.execute(
        "INSERT INTO users(org_id, role, name, email, password_hash) VALUES (?, ?, ?, ?, ?)",
        (org_id, role, name, email, hash_password(password)),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return user_id


def list_users(org_id: Optional[int] = None, db_path: Optional[str] = None):
    conn = get_conn(db_path)
    cur = conn.cursor()
    if org_id is None:
        cur.execute("SELECT id, org_id, role, name, email, created_at FROM users ORDER BY id DESC")
    else:
        cur.execute(
            "SELECT id, org_id, role, name, email, created_at FROM users WHERE org_id = ? ORDER BY id DESC",
            (org_id,),
        )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def verify_user(org_id: int, name: str, password: str, db_path: Optional[str] = None):
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, org_id, role, name FROM users WHERE org_id = ? AND name = ? AND password_hash = ?",
        (org_id, name, hash_password(password)),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def create_question(
    org_id: int,
    stem: str,
    options_json: str,
    answer: str,
    analysis: str,
    difficulty: str,
    chapter: str,
    created_by: Optional[int],
    db_path: Optional[str] = None,
) -> int:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO questions(org_id, stem, options_json, answer, analysis, difficulty, chapter, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (org_id, stem, options_json, answer, analysis, difficulty, chapter, created_by),
    )
    conn.commit()
    qid = cur.lastrowid
    conn.close()
    return qid


def list_questions(
    org_id: int,
    chapter: Optional[str] = None,
    difficulty: Optional[str] = None,
    limit: int = 50,
    db_path: Optional[str] = None,
):
    conn = get_conn(db_path)
    cur = conn.cursor()
    sql = "SELECT id, org_id, stem, options_json, answer, analysis, difficulty, chapter, created_by, created_at FROM questions WHERE org_id = ?"
    params: list = [org_id]
    if chapter:
        sql += " AND chapter = ?"
        params.append(chapter)
    if difficulty:
        sql += " AND difficulty = ?"
        params.append(difficulty)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
