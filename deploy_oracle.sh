#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#  deploy_oracle.sh — Déploiement sur Oracle Cloud Free Tier
#  VM cible : Ampere A1 Flex (4 CPU / 24 GB RAM) — GRATUIT À VIE
# ═══════════════════════════════════════════════════════════════════
set -e

# ─── COULEURS ────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
err()  { echo -e "${RED}❌ $1${NC}"; exit 1; }

echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║    🚀 DÉPLOIEMENT TRADING BOT — Oracle Cloud         ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ─── 1. MISE À JOUR SYSTÈME ──────────────────────────────────────────
echo "📦 [1/8] Mise à jour du système…"
sudo apt-get update -qq && sudo apt-get upgrade -y -qq
ok "Système à jour"

# ─── 2. INSTALLATION PYTHON ──────────────────────────────────────────
echo "🐍 [2/8] Installation Python 3.11…"
sudo apt-get install -y -qq python3.11 python3.11-venv python3-pip git
ok "Python $(python3.11 --version | cut -d' ' -f2) installé"

# ─── 3. CRÉATION UTILISATEUR DÉDIÉ ───────────────────────────────────
echo "👤 [3/8] Création utilisateur 'tradingbot'…"
if ! id "tradingbot" &>/dev/null; then
    sudo useradd -m -s /bin/bash tradingbot
    ok "Utilisateur tradingbot créé"
else
    warn "Utilisateur tradingbot existe déjà"
fi

# ─── 4. COPIE DES FICHIERS ────────────────────────────────────────────
echo "📂 [4/8] Déploiement des fichiers…"
BOT_DIR="/home/tradingbot/trading_bot"
sudo mkdir -p "$BOT_DIR"
sudo cp -r ./* "$BOT_DIR/"
sudo chown -R tradingbot:tradingbot /home/tradingbot/
ok "Fichiers copiés dans $BOT_DIR"

# ─── 5. ENVIRONNEMENT VIRTUEL ─────────────────────────────────────────
echo "🔧 [5/8] Création de l'environnement virtuel…"
sudo -u tradingbot bash -c "
    python3.11 -m venv $BOT_DIR/venv
    source $BOT_DIR/venv/bin/activate
    pip install --quiet --upgrade pip
    pip install --quiet -r $BOT_DIR/requirements.txt
"
ok "Dépendances installées"

# ─── 6. CONFIGURATION .env ────────────────────────────────────────────
echo "🔑 [6/8] Configuration des clés API…"
if [ ! -f "$BOT_DIR/.env" ]; then
    sudo -u tradingbot cp "$BOT_DIR/.env.example" "$BOT_DIR/.env"
    warn "Fichier .env créé — REMPLIS LES CLÉS AVANT DE LANCER !"
    warn "  Édite : sudo nano $BOT_DIR/.env"
else
    ok ".env déjà présent"
fi

# ─── 7. SERVICE SYSTEMD ──────────────────────────────────────────────
echo "⚙️  [7/8] Création du service systemd…"
sudo tee /etc/systemd/system/tradingbot.service > /dev/null <<EOF
[Unit]
Description=Trading Bot — Crypto + Actions
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=tradingbot
WorkingDirectory=$BOT_DIR
EnvironmentFile=$BOT_DIR/.env
ExecStart=$BOT_DIR/venv/bin/python main.py
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal
SyslogIdentifier=tradingbot

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable tradingbot
ok "Service systemd configuré"

# ─── 8. FIREWALL ─────────────────────────────────────────────────────
echo "🔒 [8/8] Configuration firewall…"
sudo apt-get install -y -qq ufw
sudo ufw default deny incoming  > /dev/null 2>&1
sudo ufw default allow outgoing > /dev/null 2>&1
sudo ufw allow ssh              > /dev/null 2>&1
sudo ufw --force enable         > /dev/null 2>&1
ok "Firewall activé (SSH autorisé)"

# ─── RÉSUMÉ ──────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ DÉPLOIEMENT TERMINÉ${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "📝 PROCHAINES ÉTAPES :"
echo ""
echo -e "  1️⃣  Remplis tes clés API :"
echo -e "     ${YELLOW}sudo nano $BOT_DIR/.env${NC}"
echo ""
echo -e "  2️⃣  Lance le bot :"
echo -e "     ${YELLOW}sudo systemctl start tradingbot${NC}"
echo ""
echo -e "  3️⃣  Vérifie qu'il tourne :"
echo -e "     ${YELLOW}sudo systemctl status tradingbot${NC}"
echo ""
echo -e "  4️⃣  Consulte les logs en direct :"
echo -e "     ${YELLOW}sudo journalctl -u tradingbot -f${NC}"
echo ""
echo -e "  5️⃣  Arrêter le bot :"
echo -e "     ${YELLOW}sudo systemctl stop tradingbot${NC}"
echo ""
