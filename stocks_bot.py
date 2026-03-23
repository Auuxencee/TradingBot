"""
stocks_bot.py — Bot actions diversifié via Alpaca Paper Trading
Stratégie : RSI seul (plus réactif) + confirmation EMA optionnelle
Tech    : NVDA, MSFT, AAPL, GOOGL, META, AMD, TSLA, AMZN
Défense : LMT, RTX, NOC, GD
Finance : JPM, GS, BRK.B
Santé   : JNJ, UNH
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from database import log_trade, init_db

load_dotenv()

ALPACA_BASE_URL = "https://paper-api.alpaca.markets"
ALPACA_API_KEY  = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET   = os.getenv("ALPACA_SECRET", "")

TECH_STOCKS    = ["NVDA", "MSFT", "AAPL", "GOOGL", "META", "AMD", "TSLA", "AMZN"]
DEFENSE_STOCKS = ["LMT", "RTX", "NOC", "GD"]
FINANCE_STOCKS = ["JPM", "GS", "BRK.B"]
HEALTH_STOCKS  = ["JNJ", "UNH"]
ALL_SYMBOLS    = TECH_STOCKS + DEFENSE_STOCKS + FINANCE_STOCKS + HEALTH_STOCKS

RSI_PERIOD   = 14
RSI_BUY      = 35   # Seuil achat relevé (était 30 — trop strict)
RSI_SELL     = 65   # Seuil vente abaissé (était 70 — trop strict)
EMA_FAST     = 9
EMA_SLOW     = 21
TRADE_USD    = 300  # USD par position (diversifié = montants plus petits)
SLEEP_SEC    = 120

HEADERS = {
    "APCA-API-KEY-ID":     ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET,
}

CATEGORY = {}
for s in TECH_STOCKS:    CATEGORY[s] = "TECH   "
for s in DEFENSE_STOCKS: CATEGORY[s] = "DEFENSE"
for s in FINANCE_STOCKS: CATEGORY[s] = "FINANCE"
for s in HEALTH_STOCKS:  CATEGORY[s] = "HEALTH "

def market_is_open() -> bool:
    try:
        resp = requests.get(f"{ALPACA_BASE_URL}/v2/clock", headers=HEADERS, timeout=10)
        return resp.json().get("is_open", False)
    except:
        return False

def get_bars(symbol: str, limit: int = 60) -> pd.DataFrame:
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

def calc_rsi(series: pd.Series, period: int = RSI_PERIOD) -> float:
    delta = series.diff()
    gain  = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss  = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rsi   = 100 - (100 / (1 + gain / loss))
    return round(float(rsi.iloc[-1]), 2)

def calc_ema(series: pd.Series, span: int) -> float:
    return float(series.ewm(span=span, adjust=False).mean().iloc[-1])

def place_order(symbol: str, side: str, qty: int):
    data = {"symbol": symbol, "qty": qty, "side": side,
            "type": "market", "time_in_force": "day"}
    resp = requests.post(f"{ALPACA_BASE_URL}/v2/orders",
                         json=data, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()

def get_positions() -> dict:
    try:
        resp = requests.get(f"{ALPACA_BASE_URL}/v2/positions", headers=HEADERS, timeout=10)
        return {p["symbol"]: float(p["qty"]) for p in resp.json()}
    except:
        return {}


class StocksBot:
    def __init__(self):
        init_db()
        self.buy_prices = {s: 0.0 for s in ALL_SYMBOLS}
        print(f"[StocksBot] Démarré — {len(ALL_SYMBOLS)} actions")
        print(f"  Tech    : {TECH_STOCKS}")
        print(f"  Défense : {DEFENSE_STOCKS}")
        print(f"  Finance : {FINANCE_STOCKS}")
        print(f"  Santé   : {HEALTH_STOCKS}")

    def analyze(self, symbol: str):
        df = get_bars(symbol)
        if df.empty or len(df) < RSI_PERIOD + 5:
            return "HOLD", 0.0, 0.0
        closes   = df["c"]
        rsi      = calc_rsi(closes)
        ema_fast = calc_ema(closes, EMA_FAST)
        ema_slow = calc_ema(closes, EMA_SLOW)
        price    = closes.iloc[-1]

        # Stratégie : RSI seul comme signal principal
        signal = "HOLD"
        if rsi < RSI_BUY:
            signal = "BUY"
        elif rsi > RSI_SELL:
            signal = "SELL"

        cat = CATEGORY.get(symbol, "OTHER  ")
        print(f"  [{cat}] {symbol:6} prix={price:.2f} RSI={rsi} → {signal}")
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
                          strategy="RSI35", signal=f"RSI={rsi}")
                print(f"    ✅ ACHAT {qty}x {symbol} @ ${price:.2f}")

            elif signal == "SELL" and in_position:
                qty = int(positions[symbol])
                place_order(symbol, "sell", qty)
                pnl = round((price - self.buy_prices[symbol]) * qty, 2)
                log_trade("stocks", symbol, "SELL", qty, price,
                          strategy="RSI35", signal=f"RSI={rsi}")
                print(f"    ✅ VENTE {qty}x {symbol} @ ${price:.2f} | PnL: {pnl:+.2f}$")
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
            time.sleep(SLEEP_SEC)

if __name__ == "__main__":
    StocksBot().run()
