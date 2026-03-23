"""
stocks_bot.py — Bot actions Tech + Défense via Alpaca Paper Trading
Stratégie : RSI (14) + EMA (9/21) — même logique que crypto_bot
Actions Tech   : NVDA, MSFT, AAPL, GOOGL
Actions Défense: LMT, RTX, NOC, GD
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from database import log_trade, init_db

load_dotenv()

# ─── CONFIG ────────────────────────────────────────────────────────────────────
ALPACA_BASE_URL  = "https://paper-api.alpaca.markets"   # Paper trading (simulation)
# ALPACA_BASE_URL = "https://api.alpaca.markets"        # ← LIVE (décommenter après 1 mois)
ALPACA_API_KEY   = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET    = os.getenv("ALPACA_SECRET", "")

TECH_STOCKS    = ["NVDA", "MSFT", "AAPL", "GOOGL"]
DEFENSE_STOCKS = ["LMT", "RTX", "NOC", "GD"]
ALL_SYMBOLS    = TECH_STOCKS + DEFENSE_STOCKS

RSI_PERIOD     = 14
RSI_OVERSOLD   = 30
RSI_OVERBOUGHT = 70
EMA_FAST       = 9
EMA_SLOW       = 21
TRADE_USD      = 500           # USD par position
SLEEP_SECONDS  = 120           # vérifie toutes les 2min (marché ouvert uniquement)

HEADERS = {
    "APCA-API-KEY-ID":     ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET,
}

# ─── HELPERS ───────────────────────────────────────────────────────────────────

def market_is_open() -> bool:
    resp = requests.get(f"{ALPACA_BASE_URL}/v2/clock", headers=HEADERS, timeout=10)
    return resp.json().get("is_open", False)

def get_bars(symbol: str, limit: int = 60) -> pd.DataFrame:
    """Récupère les barres 15min pour un symbole."""
    end   = datetime.utcnow()
    start = end - timedelta(days=5)
    url   = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars"
    params = {
        "timeframe": "15Min",
        "start":     start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end":       end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit":     limit,
        "feed":      "iex",
    }
    resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
    resp.raise_for_status()
    bars = resp.json().get("bars", [])
    if not bars:
        return pd.DataFrame()
    df = pd.DataFrame(bars)
    df["c"] = df["c"].astype(float)
    return df

def get_price(symbol: str) -> float:
    url  = f"https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest"
    resp = requests.get(url, headers=HEADERS, params={"feed": "iex"}, timeout=10)
    resp.raise_for_status()
    return float(resp.json()["quote"]["ap"])  # ask price

def calc_rsi(series: pd.Series, period: int = RSI_PERIOD) -> float:
    delta = series.diff()
    gain  = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss  = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rsi   = 100 - (100 / (1 + gain / loss))
    return round(float(rsi.iloc[-1]), 2)

def calc_ema(series: pd.Series, span: int) -> float:
    return float(series.ewm(span=span, adjust=False).mean().iloc[-1])

def place_order(symbol: str, side: str, qty: int):
    """Ordre market Alpaca (paper)."""
    data = {"symbol": symbol, "qty": qty, "side": side,
            "type": "market", "time_in_force": "day"}
    resp = requests.post(f"{ALPACA_BASE_URL}/v2/orders",
                         json=data, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()

def get_positions() -> dict:
    resp = requests.get(f"{ALPACA_BASE_URL}/v2/positions", headers=HEADERS, timeout=10)
    return {p["symbol"]: float(p["qty"]) for p in resp.json()}

# ─── STRATÉGIE ─────────────────────────────────────────────────────────────────

class StocksBot:
    def __init__(self):
        init_db()
        self.buy_prices = {s: 0.0 for s in ALL_SYMBOLS}
        print(f"[StocksBot] Démarré — {len(ALL_SYMBOLS)} actions")
        print(f"  Tech   : {TECH_STOCKS}")
        print(f"  Défense: {DEFENSE_STOCKS}")

    def categorize(self, symbol: str) -> str:
        return "tech" if symbol in TECH_STOCKS else "defense"

    def analyze(self, symbol: str):
        df = get_bars(symbol)
        if df.empty or len(df) < RSI_PERIOD + 5:
            return "HOLD", 0.0, 0.0

        closes   = df["c"]
        rsi      = calc_rsi(closes)
        ema_fast = calc_ema(closes, EMA_FAST)
        ema_slow = calc_ema(closes, EMA_SLOW)
        price    = closes.iloc[-1]

        signal = "HOLD"
        if rsi < RSI_OVERSOLD and ema_fast > ema_slow:
            signal = "BUY"
        elif rsi > RSI_OVERBOUGHT and ema_fast < ema_slow:
            signal = "SELL"

        cat = self.categorize(symbol)
        print(f"  [{cat.upper():7}] {symbol:5} prix={price:.2f} RSI={rsi} EMA9={ema_fast:.2f} EMA21={ema_slow:.2f} → {signal}")
        return signal, price, rsi

    def execute(self, symbol: str, positions: dict):
        try:
            signal, price, rsi = self.analyze(symbol)
            if price == 0:
                return

            in_position = symbol in positions and positions[symbol] > 0

            if signal == "BUY" and not in_position:
                qty = max(1, int(TRADE_USD / price))
                place_order(symbol, "buy", qty)
                self.buy_prices[symbol] = price
                log_trade("stocks", symbol, "BUY", qty, price,
                          strategy="RSI+EMA", signal=f"RSI={rsi}")
                print(f"    ✅ ACHAT {qty}x {symbol} @ ${price:.2f}")

            elif signal == "SELL" and in_position:
                qty = int(positions[symbol])
                place_order(symbol, "sell", qty)
                pnl = round((price - self.buy_prices[symbol]) * qty, 2)
                log_trade("stocks", symbol, "SELL", qty, price,
                          strategy="RSI+EMA", signal=f"RSI={rsi}")
                print(f"    ✅ VENTE {qty}x {symbol} @ ${price:.2f} | PnL: {pnl:+.2f} USD")
                self.buy_prices[symbol] = 0

        except Exception as e:
            print(f"    ❌ Erreur {symbol}: {e}")

    def run(self):
        print("[StocksBot] Boucle principale démarrée…")
        while True:
            if not market_is_open():
                print("[StocksBot] Marché fermé. Attente 5min…")
                time.sleep(300)
                continue

            print(f"\n[StocksBot] Analyse @ {datetime.utcnow().strftime('%H:%M:%S')} UTC")
            positions = get_positions()

            for sym in ALL_SYMBOLS:
                self.execute(sym, positions)

            time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    StocksBot().run()
