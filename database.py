"""
database.py — SQLite logger pour tous les trades crypto + actions
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "trades.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    NOT NULL,
            bot         TEXT    NOT NULL,   -- 'crypto' ou 'stocks'
            symbol      TEXT    NOT NULL,
            side        TEXT    NOT NULL,   -- 'BUY' ou 'SELL'
            qty         REAL    NOT NULL,
            price       REAL    NOT NULL,
            total_usd   REAL    NOT NULL,
            strategy    TEXT,
            signal      TEXT,
            status      TEXT    DEFAULT 'EXECUTED'
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS pnl_snapshots (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT NOT NULL,
            bot             TEXT NOT NULL,
            realized_pnl    REAL DEFAULT 0,
            unrealized_pnl  REAL DEFAULT 0,
            total_trades    INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def log_trade(bot: str, symbol: str, side: str, qty: float,
              price: float, strategy: str = "", signal: str = ""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO trades (timestamp, bot, symbol, side, qty, price, total_usd, strategy, signal)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.utcnow().isoformat(),
        bot, symbol, side, qty, price,
        round(qty * price, 4),
        strategy, signal
    ))
    conn.commit()
    conn.close()


def get_trades_last_hour():
    """Retourne tous les trades de la dernière heure."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT * FROM trades
        WHERE timestamp >= datetime('now', '-1 hour')
        ORDER BY timestamp DESC
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_total_pnl():
    """
    Calcule le P&L total réalisé en matchant BUY/SELL par symbole.
    Méthode FIFO simplifiée.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT DISTINCT symbol FROM trades")
    symbols = [r[0] for r in c.fetchall()]

    total_pnl = 0.0
    breakdown = {}

    for sym in symbols:
        c.execute("""
            SELECT side, qty, price FROM trades
            WHERE symbol = ? ORDER BY timestamp ASC
        """, (sym,))
        rows = c.fetchall()

        buy_queue = []  # [(qty, price), ...]
        sym_pnl = 0.0

        for row in rows:
            if row["side"] == "BUY":
                buy_queue.append([row["qty"], row["price"]])
            elif row["side"] == "SELL":
                sell_qty = row["qty"]
                sell_price = row["price"]
                while sell_qty > 0 and buy_queue:
                    bq, bp = buy_queue[0]
                    matched = min(bq, sell_qty)
                    sym_pnl += matched * (sell_price - bp)
                    sell_qty -= matched
                    buy_queue[0][0] -= matched
                    if buy_queue[0][0] <= 1e-9:
                        buy_queue.pop(0)

        breakdown[sym] = round(sym_pnl, 4)
        total_pnl += sym_pnl

    conn.close()
    return round(total_pnl, 4), breakdown


def get_today_pnl():
    """P&L réalisé uniquement aujourd'hui (UTC)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT symbol, side, qty, price FROM trades
        WHERE timestamp >= date('now')
        ORDER BY symbol, timestamp ASC
    """)
    rows = c.fetchall()
    conn.close()

    by_sym = {}
    for r in rows:
        by_sym.setdefault(r["symbol"], []).append(dict(r))

    today_pnl = 0.0
    for sym, trades in by_sym.items():
        buys = []
        for t in trades:
            if t["side"] == "BUY":
                buys.append([t["qty"], t["price"]])
            elif t["side"] == "SELL":
                sq = t["qty"]
                sp = t["price"]
                while sq > 0 and buys:
                    bq, bp = buys[0]
                    m = min(bq, sq)
                    today_pnl += m * (sp - bp)
                    sq -= m
                    buys[0][0] -= m
                    if buys[0][0] <= 1e-9:
                        buys.pop(0)

    return round(today_pnl, 4)
