"""
main.py — Orchestrateur principal
Lance les 3 composants en threads parallèles :
  1. crypto_bot   → Binance Testnet
  2. stocks_bot   → Alpaca Paper Trading
  3. telegram_alerts → rapports horaires
"""

import threading
import time
import signal
import sys
from datetime import datetime, UTC

from database import init_db
from crypto_bot import CryptoBot
from stocks_bot import StocksBot
from telegram_alerts import run_scheduler

# ─── INIT ──────────────────────────────────────────────────────────────────────

def banner():
    print("""
╔══════════════════════════════════════════════════════╗
║          🤖  TRADING BOT — DÉMARRAGE               ║
║  Crypto  : BTC/USDT · ETH/USDT  (Binance Testnet) ║
║  Actions : NVDA · MSFT · AAPL · GOOGL             ║
║  Défense : LMT · RTX · NOC · GD  (Alpaca Paper)  ║
║  Alertes : Telegram — toutes les heures           ║
╚══════════════════════════════════════════════════════╝
""")

def graceful_exit(signum, frame):
    print("\n[Main] Signal reçu — arrêt propre…")
    sys.exit(0)

# ─── THREADS ───────────────────────────────────────────────────────────────────

def run_crypto():
    try:
        bot = CryptoBot()
        bot.run()
    except Exception as e:
        print(f"[CryptoBot] CRASH: {e}")

def run_stocks():
    try:
        bot = StocksBot()
        bot.run()
    except Exception as e:
        print(f"[StocksBot] CRASH: {e}")

def run_alerts():
    try:
        run_scheduler()
    except Exception as e:
        print(f"[Alerts] CRASH: {e}")

# ─── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    banner()
    signal.signal(signal.SIGINT,  graceful_exit)
    signal.signal(signal.SIGTERM, graceful_exit)

    print("[Main] Initialisation base de données…")
    init_db()
    print("[Main] DB OK ✅\n")

    threads = [
        threading.Thread(target=run_crypto,  name="CryptoBot",  daemon=True),
        threading.Thread(target=run_stocks,  name="StocksBot",  daemon=True),
        threading.Thread(target=run_alerts,  name="TelegramBot", daemon=True),
    ]

    for t in threads:
        print(f"[Main] Démarrage thread: {t.name}")
        t.start()
        time.sleep(2)

    print(f"\n[Main] ✅ Tous les bots actifs @ {datetime.now(UTC).strftime('%H:%M:%S')} UTC")
    print("[Main] Ctrl+C pour arrêter\n")

    # Watchdog — redémarre un thread s'il crashe
    while True:
        for t in threads:
            if not t.is_alive():
                print(f"[Main] ⚠️  Thread {t.name} mort — redémarrage…")
                if t.name == "CryptoBot":
                    nt = threading.Thread(target=run_crypto, name="CryptoBot", daemon=True)
                elif t.name == "StocksBot":
                    nt = threading.Thread(target=run_stocks, name="StocksBot", daemon=True)
                else:
                    nt = threading.Thread(target=run_alerts, name="TelegramBot", daemon=True)
                nt.start()
                threads[threads.index(t)] = nt
        time.sleep(30)
