# 🤖 Trading Bot — Crypto + Actions Tech/Défense

Bot de trading automatisé avec alertes Telegram horaires.
Fonctionne en simulation gratuite (Binance Testnet + Alpaca Paper Trading).

---

## 📦 Fichiers du projet

```
trading_bot/
├── main.py              ← Orchestrateur (lance tout)
├── crypto_bot.py        ← Bot crypto Binance Testnet
├── stocks_bot.py        ← Bot actions Alpaca Paper
├── telegram_alerts.py   ← Rapports Telegram horaires
├── database.py          ← SQLite — log de tous les trades
├── requirements.txt     ← Dépendances Python
├── .env.example         ← Template clés API
└── deploy_oracle.sh     ← Script déploiement Oracle Cloud
```

---

## 🚀 ÉTAPE 1 — Créer tes comptes gratuits (15 min)

### A) Binance Testnet (Crypto)

1. Va sur https://testnet.binance.vision/
2. Connecte-toi avec GitHub
3. Clique **"Generate HMAC_SHA256 Key"**
4. Copie **API Key** et **Secret Key**

### B) Alpaca Paper Trading (Actions)

1. Va sur https://alpaca.markets/
2. Crée un compte gratuit
3. Dans le dashboard → **Paper Trading**
4. Clique sur **"View" API Keys** → copie les clés

### C) Bot Telegram

1. Ouvre Telegram → cherche **@BotFather**
2. Envoie `/newbot`
3. Donne un nom (ex: `MonTradingBot`)
4. Copie le **token** fourni
5. Envoie un message à ton nouveau bot
6. Va sur : `https://api.telegram.org/bot<TON_TOKEN>/getUpdates`
7. Copie le **"id"** dans `"chat":{"id":XXXXXXX}`

---

## 🔑 ÉTAPE 2 — Configurer les clés

```bash
cp .env.example .env
nano .env
```

Remplis les 5 valeurs :

```
BINANCE_API_KEY=...
BINANCE_SECRET=...
ALPACA_API_KEY=...
ALPACA_SECRET=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

---

## 🐍 ÉTAPE 3 — Installer et lancer (local pour tester)

```bash
# Créer l'environnement virtuel
python3 -m venv venv
source venv/bin/activate        # Linux/Mac
# ou : venv\Scripts\activate    # Windows

# Installer les dépendances
pip install -r requirements.txt

# Lancer
python main.py
```

---

## ☁️ ÉTAPE 4 — Déployer sur Oracle Cloud Free Tier

### Créer la VM gratuite

1. Va sur https://cloud.oracle.com/ → Crée un compte (carte bancaire demandée mais **0€ débité**)
2. Dans la console → **Compute** → **Instances** → **Create Instance**
3. Choisis :
   - **Image** : Ubuntu 22.04
   - **Shape** : `VM.Standard.A1.Flex` ← GRATUIT (4 CPU, 24GB RAM)
   - Génère ou upload ta clé SSH
4. Lance l'instance

### Se connecter à la VM

```bash
ssh -i ta_cle_privee.pem ubuntu@IP_DE_TA_VM
```

### Déployer le bot

```bash
# Copier les fichiers sur la VM
scp -i ta_cle.pem -r ./trading_bot ubuntu@IP_VM:~/

# Se connecter à la VM
ssh -i ta_cle.pem ubuntu@IP_VM

# Lancer le script de déploiement
cd trading_bot
chmod +x deploy_oracle.sh
./deploy_oracle.sh

# Remplir les clés API
sudo nano /home/tradingbot/trading_bot/.env

# Démarrer le bot
sudo systemctl start tradingbot

# Vérifier
sudo systemctl status tradingbot
```

### Voir les logs en direct

```bash
sudo journalctl -u tradingbot -f
```

---

## 📱 Format des alertes Telegram

```
━━━━━━━━━━━━━━━━━━━━━━━━
📊 RAPPORT HORAIRE
🕐 22/03/2026 14:00 UTC
━━━━━━━━━━━━━━━━━━━━━━━━

📋 3 trade(s) cette heure

🪙 CRYPTO
  🟢 ACHAT BTCUSDT
    💲 Prix: $83,240.00 | 💰 Montant: $100.00
    🕐 2026-03-22 13:12 UTC

  🔴 VENTE BTCUSDT
    💲 Prix: $84,100.00 | 💰 Montant: $101.04
    🕐 2026-03-22 13:47 UTC

📈 STOCKS
  🟢 ACHAT NVDA
    💲 Prix: $875.50 | 💰 Montant: $500.00
    🕐 2026-03-22 13:30 UTC

━━━━━━━━━━━━━━━━━━━━━━━━
💰 GAINS / PERTES
  📈 Aujourd'hui : +$87.42
  🏆 Total cumulé : +$87.42
━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## ⚠️ Passage en mode RÉEL (après 1 mois)

Dans `crypto_bot.py` :

```python
# Décommenter ces lignes :
# place_order(symbol, "BUY", qty)
# place_order(symbol, "SELL", qty)
```

Dans `stocks_bot.py` :

```python
# Changer l'URL :
ALPACA_BASE_URL = "https://api.alpaca.markets"  # ← LIVE
```

---

## 🛡️ Sécurité

- Ne jamais partager le fichier `.env`
- Ajouter `.env` dans `.gitignore` si tu utilises Git
- Sur Oracle, seul le port SSH (22) est ouvert
