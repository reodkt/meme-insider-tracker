"""
SQLite storage layer for tokens, wallets, and insider events.
"""

import sqlite3
import json
import os
from datetime import datetime
from core.config import DB_PATH


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chain TEXT NOT NULL,
            address TEXT NOT NULL,
            symbol TEXT,
            name TEXT,
            pair_address TEXT,
            dex TEXT,
            liquidity_usd REAL DEFAULT 0,
            market_cap REAL DEFAULT 0,
            price_usd REAL DEFAULT 0,
            volume_24h REAL DEFAULT 0,
            created_at TEXT,
            first_seen TEXT DEFAULT (datetime('now')),
            last_updated TEXT DEFAULT (datetime('now')),
            UNIQUE(chain, address)
        );

        CREATE TABLE IF NOT EXISTS wallets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chain TEXT NOT NULL,
            address TEXT NOT NULL,
            label TEXT,
            tags TEXT DEFAULT '[]',
            funded_by TEXT,
            first_seen TEXT DEFAULT (datetime('now')),
            UNIQUE(chain, address)
        );

        CREATE TABLE IF NOT EXISTS insider_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chain TEXT NOT NULL,
            token_address TEXT NOT NULL,
            wallet_address TEXT NOT NULL,
            event_type TEXT NOT NULL,
            severity TEXT DEFAULT 'medium',
            details TEXT DEFAULT '{}',
            amount_usd REAL DEFAULT 0,
            tx_hash TEXT,
            block_number INTEGER,
            detected_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS wallet_clusters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chain TEXT NOT NULL,
            funder_address TEXT NOT NULL,
            wallet_addresses TEXT DEFAULT '[]',
            token_address TEXT,
            cluster_size INTEGER DEFAULT 0,
            total_bought_usd REAL DEFAULT 0,
            detected_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_tokens_chain ON tokens(chain);
        CREATE INDEX IF NOT EXISTS idx_events_token ON insider_events(token_address);
        CREATE INDEX IF NOT EXISTS idx_events_type ON insider_events(event_type);
        CREATE INDEX IF NOT EXISTS idx_events_severity ON insider_events(severity);
        CREATE INDEX IF NOT EXISTS idx_clusters_funder ON wallet_clusters(funder_address);
    """)
    conn.close()


def upsert_token(chain, address, **kwargs):
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM tokens WHERE chain=? AND address=?",
        (chain, address.lower())
    ).fetchone()

    if existing:
        sets = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [chain, address.lower()]
        conn.execute(
            f"UPDATE tokens SET {sets}, last_updated=datetime('now') WHERE chain=? AND address=?",
            vals
        )
    else:
        kwargs["chain"] = chain
        kwargs["address"] = address.lower()
        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join("?" for _ in kwargs)
        conn.execute(f"INSERT INTO tokens ({cols}) VALUES ({placeholders})", list(kwargs.values()))

    conn.commit()
    conn.close()


def add_insider_event(chain, token_address, wallet_address, event_type,
                      severity="medium", details=None, amount_usd=0,
                      tx_hash=None, block_number=None):
    conn = get_db()
    conn.execute("""
        INSERT INTO insider_events
        (chain, token_address, wallet_address, event_type, severity, details,
         amount_usd, tx_hash, block_number)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        chain, token_address.lower(), wallet_address.lower(), event_type,
        severity, json.dumps(details or {}), amount_usd, tx_hash, block_number
    ))
    conn.commit()
    conn.close()


def add_wallet_cluster(chain, funder_address, wallet_addresses,
                       token_address=None, total_bought_usd=0):
    conn = get_db()
    conn.execute("""
        INSERT INTO wallet_clusters
        (chain, funder_address, wallet_addresses, token_address,
         cluster_size, total_bought_usd)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        chain, funder_address.lower(), json.dumps(wallet_addresses),
        token_address, len(wallet_addresses), total_bought_usd
    ))
    conn.commit()
    conn.close()


def get_recent_events(limit=100, chain=None, severity=None):
    conn = get_db()
    query = "SELECT * FROM insider_events WHERE 1=1"
    params = []
    if chain:
        query += " AND chain=?"
        params.append(chain)
    if severity:
        query += " AND severity=?"
        params.append(severity)
    query += " ORDER BY detected_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_tracked_tokens(limit=200, chain=None):
    conn = get_db()
    query = "SELECT * FROM tokens WHERE 1=1"
    params = []
    if chain:
        query += " AND chain=?"
        params.append(chain)
    query += " ORDER BY last_updated DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_clusters(limit=50, chain=None):
    conn = get_db()
    query = "SELECT * FROM wallet_clusters WHERE 1=1"
    params = []
    if chain:
        query += " AND chain=?"
        params.append(chain)
    query += " ORDER BY detected_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]
