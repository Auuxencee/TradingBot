"""
crypto_bot.py — Données via CoinGecko (aucune restriction géo)
Stratégie : RSI (14) + EMA (9/21)
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from database import log_trade, init_db
import telegram_alerts

load_dotenv()

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
COINS = {"BTCUSDT": "bitcoin", "ETHUSDT": "ethereum"}
PAIRS          = ["BTCUSDT", "ETHUSDT"]
RSI_PERIOD     = 14
RSI_OVERSOLD   = 30
RSI_OVERBOUGHT = 70
EMA_FAST       = 9
EMA_SLOW       = 21
TRADE_AMOUNT   = 100
SLEEP_SECONDS  = 600   # CoinGecko gratuit — 10 min entre chaque cycle

def get_klines(coin_id: str, days: int = 3) -> pd.DataFrame:
    resp = requests.get(f"{COINGECKO_BASE}/coins/{coin_id}/market_chart",
        params={"vs_currency": "usd", "days": days, "interval": "hourly"},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15)
    resp.raise_for_status()
    prices = resp.json()["prices"]
    df = pd.DataFrame(prices, columns=["ts", "close"])
    df["close"] = df["close"].astype(float)
    return df

def get_price(coin_id: str) -> float:
    resp = requests.get(f"{COINGECKO_BASE}/simple/price",
        params={"ids": coin_id, "vs_currencies": "usd"}, timeout=10)
    resp.raise_for_status()
    return float(resp.json()[coin_id]["usd"])

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
        print(f"[CryptoBot] Démarré — CoinGecko — paires: {PAIRS}")

    def analyze(self, symbol):
        coin_id  = COINS[symbol]
        df       = get_klines(coin_id)
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
        print(f"[{symbol}] prix=${price:,.2f} RSI={rsi} EMA9={ema_fast:.2f} EMA21={ema_slow:.2f} → {signal}")
        telegram_alerts.update_price(symbol, price)
        return signal, price, rsi

    def execute(self, symbol):
        try:
            signal, price, rsi = self.analyze(symbol)
            if signal == "BUY" and self.positions[symbol] == 0:
                qty = round(TRADE_AMOUNT / price, 6)
                self.positions[symbol]  = qty
                self.buy_prices[symbol] = price
                log_trade("crypto", symbol, "BUY", qty, price, strategy="RSI+EMA", signal=f"RSI={rsi}")
                print(f"  ✅ ACHAT {qty} {symbol} @ ${price:,.2f}")
            elif signal == "SELL" and self.positions[symbol] > 0:
                qty = self.positions[symbol]
                pnl = round((price - self.buy_prices[symbol]) * qty, 4)
                log_trade("crypto", symbol, "SELL", qty, price, strategy="RSI+EMA", signal=f"RSI={rsi}")
                print(f"  ✅ VENTE {qty} {symbol} @ ${price:,.2f} | PnL: {pnl:+.4f} USD")
                self.positions[symbol]  = 0
                self.buy_prices[symbol] = 0
        except Exception as e:
            print(f"  ❌ Erreur {symbol}: {e}")
        time.sleep(15)  # 15s entre les 2 paires pour éviter le rate limit

    def run(self):
        print("[CryptoBot] Boucle principale démarrée…")
        while True:
            for pair in PAIRS:
                self.execute(pair)
            time.sleep(SLEEP_SECONDS)

if __name__ == "__main__":
    CryptoBot().run()
