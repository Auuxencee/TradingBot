"""
telegram_alerts.py — Alertes Telegram toutes les heures
Résumé : trades de l'heure passée + prix achat/vente + gains totaux
"""

import os
import requests
import schedule
import time
from datetime import datetime
from dotenv import load_dotenv
from database import get_trades_last_hour, get_total_pnl, get_today_pnl

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

# Prix en mémoire pour le résumé marché
_last_prices = {}

def update_price(symbol: str, price: float):
    """Appelé par les bots pour garder les derniers prix."""
    _last_prices[symbol] = price

def send_telegram(message: str):
    url  = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    resp = requests.post(url, json=data, timeout=10)
    if not resp.ok:
        print(f"[Telegram] Erreur envoi: {resp.text}")
    else:
        print("[Telegram] Message envoyé ✅")


def format_side_emoji(side: str) -> str:
    return "🟢 ACHAT" if side == "BUY" else "🔴 VENTE"

def format_bot_section(trades: list, bot_name: str, emoji: str) -> str:
    bot_trades = [t for t in trades if t["bot"] == bot_name]
    if not bot_trades:
        return ""
    lines = [f"\n{emoji} <b>{bot_name.upper()}</b>"]
    for t in bot_trades:
        ts    = t["timestamp"][:16].replace("T", " ")
        side  = format_side_emoji(t["side"])
        price = f"${t['price']:,.4f}" if t["price"] < 1000 else f"${t['price']:,.2f}"
        total = f"${t['total_usd']:,.2f}"
        sig   = f" ({t['signal']})" if t.get("signal") else ""
        lines.append(
            f"  {side} <code>{t['symbol']}</code>\n"
            f"    💲 Prix: {price} | 💰 Montant: {total}{sig}\n"
            f"    🕐 {ts} UTC"
        )
    return "\n".join(lines)

def build_market_snapshot() -> str:
    """Prix actuels des actifs surveillés."""
    if not _last_prices:
        return ""
    lines = ["\n📡 <b>MARCHÉS EN DIRECT</b>"]
    crypto  = {k: v for k, v in _last_prices.items() if k in ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT"]}
    stocks  = {k: v for k, v in _last_prices.items() if k not in crypto}
    if crypto:
        lines.append("  🪙 Crypto:")
        for sym, price in crypto.items():
            name = sym.replace("USDT","")
            lines.append(f"    {name}: <b>${price:,.2f}</b>")
    if stocks:
        lines.append("  📈 Actions:")
        for sym, price in sorted(stocks.items()):
            lines.append(f"    {sym}: <b>${price:,.2f}</b>")
    return "\n".join(lines)


def build_hourly_report() -> str:
    now    = datetime.utcnow().strftime("%d/%m/%Y %H:%M")
    trades = get_trades_last_hour()
    total_pnl, breakdown = get_total_pnl()
    today_pnl            = get_today_pnl()

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📊 <b>RAPPORT HORAIRE</b>",
        f"🕐 {now} UTC",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    # Trades de l'heure
    if not trades:
        lines.append("\n💤 <i>Aucun trade cette heure</i>")
        lines.append("   (En attente de signaux RSI)")
    else:
        lines.append(f"\n📋 <b>{len(trades)} trade(s) cette heure</b>")
        cs = format_bot_section(trades, "crypto", "🪙")
        ss = format_bot_section(trades, "stocks", "📈")
        if cs: lines.append(cs)
        if ss: lines.append(ss)

    # Snapshot marché
    snapshot = build_market_snapshot()
    if snapshot:
        lines.append(snapshot)

    # P&L
    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("💰 <b>GAINS / PERTES</b>")
    today_sign  = "+" if today_pnl >= 0 else ""
    total_sign  = "+" if total_pnl >= 0 else ""
    today_emoji = "📈" if today_pnl >= 0 else "📉"
    total_emoji = "🏆" if total_pnl >= 0 else "⚠️"
    lines.append(f"  {today_emoji} Aujourd'hui : <b>{today_sign}${today_pnl:,.2f}</b>")
    lines.append(f"  {total_emoji} Total cumulé : <b>{total_sign}${total_pnl:,.2f}</b>")

    if breakdown:
        details = [(s, p) for s, p in breakdown.items() if abs(p) > 0.01]
        if details:
            lines.append("\n  <i>Détail par actif:</i>")
            for sym, pnl in sorted(details, key=lambda x: -abs(x[1])):
                sign = "+" if pnl >= 0 else ""
                icon = "▲" if pnl >= 0 else "▼"
                lines.append(f"    {icon} {sym}: {sign}${pnl:,.4f}")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)

def send_hourly_report():
    print(f"[Telegram] Envoi rapport @ {datetime.utcnow().strftime('%H:%M')} UTC")
    send_telegram(build_hourly_report())

def send_startup_message():
    msg = (
        "🚀 <b>BOT TRADING DÉMARRÉ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🪙 Crypto  : BTC · ETH (CoinGecko)\n"
        "📈 Tech    : NVDA · MSFT · AAPL · GOOGL · META · AMD · TSLA · AMZN\n"
        "🛡️ Défense : LMT · RTX · NOC · GD\n"
        "💰 Finance : JPM · GS · BRK.B\n"
        "🏥 Santé   : JNJ · UNH\n"
        "📊 Stratégie : RSI &lt;35 achat / &gt;65 vente\n"
        "⏰ Rapports : toutes les heures\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Mode : <b>SIMULATION</b> 🧪"
    )
    send_telegram(msg)

def run_scheduler():
    send_startup_message()
    schedule.every().hour.at(":00").do(send_hourly_report)
    print("[Scheduler] Alertes Telegram actives — rapport toutes les heures")
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    run_scheduler()
