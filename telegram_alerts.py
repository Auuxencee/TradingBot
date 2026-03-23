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

# ─── CONFIG ────────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

def send_telegram(message: str):
    url  = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       message,
        "parse_mode": "HTML",
    }
    resp = requests.post(url, json=data, timeout=10)
    if not resp.ok:
        print(f"[Telegram] Erreur envoi: {resp.text}")
    else:
        print("[Telegram] Message envoyé ✅")

# ─── FORMATAGE DU RAPPORT ──────────────────────────────────────────────────────

def format_side_emoji(side: str) -> str:
    return "🟢 ACHAT" if side == "BUY" else "🔴 VENTE"

def format_bot_section(trades: list, bot_name: str, emoji: str) -> str:
    bot_trades = [t for t in trades if t["bot"] == bot_name]
    if not bot_trades:
        return ""

    lines = [f"\n{emoji} <b>{bot_name.upper()}</b>"]
    for t in bot_trades:
        ts     = t["timestamp"][:16].replace("T", " ")
        side   = format_side_emoji(t["side"])
        sym    = t["symbol"]
        price  = f"${t['price']:,.4f}" if t["price"] < 1000 else f"${t['price']:,.2f}"
        total  = f"${t['total_usd']:,.2f}"
        signal = f" ({t['signal']})" if t.get("signal") else ""
        lines.append(
            f"  {side} <code>{sym}</code>\n"
            f"    💲 Prix: {price} | 💰 Montant: {total}{signal}\n"
            f"    🕐 {ts} UTC"
        )

    return "\n".join(lines)


def build_hourly_report() -> str:
    now    = datetime.utcnow().strftime("%d/%m/%Y %H:%M")
    trades = get_trades_last_hour()

    total_pnl, breakdown = get_total_pnl()
    today_pnl            = get_today_pnl()

    # ── En-tête ────────────────────────────────────────────────
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📊 <b>RAPPORT HORAIRE</b>",
        f"🕐 {now} UTC",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    # ── Trades de l'heure ──────────────────────────────────────
    if not trades:
        lines.append("\n💤 Aucune action cette heure")
    else:
        lines.append(f"\n📋 <b>{len(trades)} trade(s) cette heure</b>")
        crypto_section = format_bot_section(trades, "crypto", "🪙")
        stocks_section = format_bot_section(trades, "stocks", "📈")
        if crypto_section:
            lines.append(crypto_section)
        if stocks_section:
            lines.append(stocks_section)

    # ── P&L ────────────────────────────────────────────────────
    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("💰 <b>GAINS / PERTES</b>")

    today_sign = "+" if today_pnl >= 0 else ""
    total_sign = "+" if total_pnl >= 0 else ""
    today_emoji = "📈" if today_pnl >= 0 else "📉"
    total_emoji = "🏆" if total_pnl >= 0 else "⚠️"

    lines.append(f"  {today_emoji} Aujourd'hui : <b>{today_sign}${today_pnl:,.2f}</b>")
    lines.append(f"  {total_emoji} Total cumulé : <b>{total_sign}${total_pnl:,.2f}</b>")

    # Détail par symbole si gains/pertes non nuls
    if breakdown:
        detail_lines = []
        for sym, pnl in sorted(breakdown.items(), key=lambda x: -abs(x[1])):
            if abs(pnl) > 0.01:
                sign = "+" if pnl >= 0 else ""
                icon = "▲" if pnl >= 0 else "▼"
                detail_lines.append(f"    {icon} {sym}: {sign}${pnl:,.4f}")
        if detail_lines:
            lines.append("\n  <i>Détail par actif:</i>")
            lines.extend(detail_lines)

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


# ─── SCHEDULER ─────────────────────────────────────────────────────────────────

def send_hourly_report():
    print(f"[Telegram] Envoi rapport @ {datetime.utcnow().strftime('%H:%M')} UTC")
    msg = build_hourly_report()
    send_telegram(msg)


def send_startup_message():
    msg = (
        "🚀 <b>BOT TRADING DÉMARRÉ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🪙 Crypto  : BTC/USDT, ETH/USDT\n"
        "📈 Tech    : NVDA, MSFT, AAPL, GOOGL\n"
        "🛡️ Défense : LMT, RTX, NOC, GD\n"
        "📊 Stratégie : RSI(14) + EMA(9/21)\n"
        "⏰ Rapports : toutes les heures\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Mode : <b>SIMULATION</b> 🧪"
    )
    send_telegram(msg)


def run_scheduler():
    send_startup_message()

    # Rapport toutes les heures pile (00min)
    schedule.every().hour.at(":00").do(send_hourly_report)

    print("[Scheduler] Alertes Telegram actives — rapport toutes les heures")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    run_scheduler()
