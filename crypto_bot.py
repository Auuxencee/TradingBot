"""
crypto_bot.py — Bot crypto Bybit (sans restriction géo)
Stratégie : RSI (14) + EMA (9/21)
"""

import os
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
from database import log_trade, init_db

load_dotenv()

BYBIT_BASE     = "https://api.bybit.com"
PAIRS          = ["BTCUSDT", "ETHUSDT"]
INTERVAL       = "15"
RSI_PERIOD     = 14
RSI_OVERSOLD   = 30
RSI_OVERBOUGHT = 70
EMA_FAST       = 9
EMA_SLOW       = 21
TRADE_AMOUNT   = 100
SLEEP_SECONDS  = 60

def get_klines(symbol, interval=INTERVAL, limit=100):
    resp = requests.get(f"{BYBIT_BASE}/v5/market/kline", params={
        "category": "spot", "symbol": symbol,
        "interval": interval, "limit": limit,
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data.get("retCode") != 0:
        raise Exception(f"Bybit: {data.get('retMsg')}")
    rows = data["result"]["list"]
    df = pd.DataFrame(rows, columns=["ts","open","high","low","close","volume","turnover"])
    df["close"] = df["close"].astype(float)
    return df.iloc[::-1].reset_index(drop=True)

def get_price(symbol):
    resp = requests.get(f"{BYBIT_BASE}/v5/market/tickers",
                        params={"category": "spot", "symbol": symbol}, timeout=10)
    return float(resp.json()["result"]["list"][0]["lastPrice"])

def calc_rsi(series, period=RSI_PERIOD):
    delta = series.diff()
    gain  = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss  = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    return round(float((100 - (100 / (1 + gain / loss))).iloc[-1]), 2)

def calc_ema(series, span):
    return float(series.ewm(span=span, adjust=False).mean().iloc[-1])

class CryptoBot:
    def __init__(self):
        init_db()
        self.positions  = {p: 0.0 for p in PAIRS}
        self.buy_prices = {p: 0.0 for p in PAIRS}
        print(f"[CryptoBot] Démarré — Bybit — paires: {PAIRS}")

    def analyze(self, symbol):
        df       = get_klines(symbol)
        closes   = df["close"]
        rsi      = calc_rsi(closes)
        ema_fast = calc_ema(closes, EMA_FAST)
        ema_slow = calc_ema(closes, EMA_SLOW)
        price    = closes.iloc[-1]
        signal   = "HOLD"
        if rsi < RSI_OVERSOLD and ema_fast > ema_slow:
            signal = "BUY"
        elif rsi > RSI_OVERBOUGHT and ema_fast < ema_slow:
            signal = "SELL"
        print(f"[{symbol}] prix={price:.4f} RSI={rsi} EMA9={ema_fast:.2f} EMA21={ema_slow:.2f} → {signal}")
        return signal, price, rsi

    def execute(self, symbol):
        try:
            signal, price, rsi = self.analyze(symbol)
            if signal == "BUY" and self.positions[symbol] == 0:
                qty = round(TRADE_AMOUNT / price, 6)
                self.positions[symbol]  = qty
                self.buy_prices[symbol] = price
                log_trade("crypto", symbol, "BUY", qty, price, strategy="RSI+EMA", signal=f"RSI={rsi}")
                print(f"  ✅ ACHAT {qty} {symbol} @ {price}")
            elif signal == "SELL" and self.positions[symbol] > 0:
                qty = self.positions[symbol]
                pnl = round((price - self.buy_prices[symbol]) * qty, 4)
                log_trade("crypto", symbol, "SELL", qty, price, strategy="RSI+EMA", signal=f"RSI={rsi}")
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
