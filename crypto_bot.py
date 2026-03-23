"""
crypto_bot.py — Bot crypto Binance Testnet
Stratégie : RSI (14) + EMA (9/21) crossover
Paires : BTC/USDT, ETH/USDT
"""

import os
import time
import hmac
import hashlib
import requests
import pandas as pd
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
from database import log_trade, init_db

load_dotenv()

# ─── CONFIG ────────────────────────────────────────────────────────────────────
BINANCE_TESTNET_BASE = "https://api.binance.com/api"  # API publique — pas de restriction géo
API_KEY    = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_SECRET", "")

PAIRS          = ["BTCUSDT", "ETHUSDT"]
INTERVAL       = "15m"         # bougie 15 minutes
RSI_PERIOD     = 14
RSI_OVERSOLD   = 30            # signal ACHAT
RSI_OVERBOUGHT = 70            # signal VENTE
EMA_FAST       = 9
EMA_SLOW       = 21
TRADE_AMOUNT   = 100           # USD par trade (simulation)
SLEEP_SECONDS  = 60            # vérifie toutes les 60s

# ─── HELPERS ───────────────────────────────────────────────────────────────────

def _sign(params: dict) -> str:
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return hmac.new(API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()

def get_klines(symbol: str, interval: str = INTERVAL, limit: int = 100) -> pd.DataFrame:
    url = f"{BINANCE_TESTNET_BASE}/v3/klines"
    resp = requests.get(url, params={"symbol": symbol, "interval": interval, "limit": limit},
                        timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    data = resp.json()
    df = pd.DataFrame(data, columns=[
        "open_time","open","high","low","close","volume",
        "close_time","qav","trades","tbbav","tbqav","ignore"
    ])
    df["close"] = df["close"].astype(float)
    df["open"]  = df["open"].astype(float)
    return df

def calc_rsi(series: pd.Series, period: int = RSI_PERIOD) -> float:
    delta  = series.diff()
    gain   = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss   = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs     = gain / loss
    rsi    = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)

def calc_ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()

def get_price(symbol: str) -> float:
    url  = f"{BINANCE_TESTNET_BASE}/v3/ticker/price"
    resp = requests.get(url, params={"symbol": symbol},
                        timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    return float(resp.json()["price"])

def place_order(symbol: str, side: str, qty: float) -> dict:
    """Place un ordre market sur le testnet."""
    ts     = int(time.time() * 1000)
    params = {
        "symbol":    symbol,
        "side":      side,
        "type":      "MARKET",
        "quantity":  round(qty, 6),
        "timestamp": ts,
    }
    params["signature"] = _sign(params)
    url  = f"{BINANCE_TESTNET_BASE}/v3/order"
    resp = requests.post(url, params=params,
                         headers={"X-MBX-APIKEY": API_KEY}, timeout=10)
    resp.raise_for_status()
    return resp.json()

# ─── STRATÉGIE ─────────────────────────────────────────────────────────────────

class CryptoBot:
    def __init__(self):
        init_db()
        self.positions = {p: 0.0 for p in PAIRS}  # qty détenue
        self.buy_prices = {p: 0.0 for p in PAIRS}
        print(f"[CryptoBot] Démarré — paires: {PAIRS}")

    def analyze(self, symbol: str):
        df      = get_klines(symbol)
        closes  = df["close"]
        rsi     = calc_rsi(closes)
        ema_fast = calc_ema(closes, EMA_FAST).iloc[-1]
        ema_slow = calc_ema(closes, EMA_SLOW).iloc[-1]
        price   = closes.iloc[-1]

        signal = "HOLD"
        if rsi < RSI_OVERSOLD and ema_fast > ema_slow:
            signal = "BUY"
        elif rsi > RSI_OVERBOUGHT and ema_fast < ema_slow:
            signal = "SELL"

        print(f"[{symbol}] prix={price:.4f} RSI={rsi} EMA9={ema_fast:.4f} EMA21={ema_slow:.4f} → {signal}")
        return signal, price, rsi

    def execute(self, symbol: str):
        try:
            signal, price, rsi = self.analyze(symbol)

            if signal == "BUY" and self.positions[symbol] == 0:
                qty = round(TRADE_AMOUNT / price, 6)
                # place_order(symbol, "BUY", qty)   # ← décommenter sur testnet réel
                self.positions[symbol]  = qty
                self.buy_prices[symbol] = price
                log_trade("crypto", symbol, "BUY", qty, price,
                          strategy="RSI+EMA", signal=f"RSI={rsi}")
                print(f"  ✅ ACHAT {qty} {symbol} @ {price}")

            elif signal == "SELL" and self.positions[symbol] > 0:
                qty   = self.positions[symbol]
                # place_order(symbol, "SELL", qty)  # ← décommenter sur testnet réel
                log_trade("crypto", symbol, "SELL", qty, price,
                          strategy="RSI+EMA", signal=f"RSI={rsi}")
                pnl = round((price - self.buy_prices[symbol]) * qty, 4)
                print(f"  ✅ VENTE {qty} {symbol} @ {price} | PnL: {pnl:+.4f} USD")
                self.positions[symbol]  = 0
                self.buy_prices[symbol] = 0

        except Exception as e:
            print(f"  ❌ Erreur {symbol}: {e}")

    def run(self):
        print("[CryptoBot] Boucle principale démarrée…")
        while True:
            for pair in PAIRS:
                self.execute(pair)
            time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    CryptoBot().run()
