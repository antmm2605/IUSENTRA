#!/usr/bin/env bash
# bootstrap_ubuntu.sh — prepara Ubuntu 22/24 LTS su Hetzner CPX42 per IUSENTRA
# Eseguire come root sul server pulito.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Eseguire come root." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

# ---------------------------------------------------------------------------
# 1. Pacchetti base + sicurezza
# ---------------------------------------------------------------------------
apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  fail2ban \
  git \
  gnupg \
  jq \
  logrotate \
  openssl \
  opensc \
  pcscd \
  rsync \
  unattended-upgrades \
  unzip \
  ufw \
  zstd

# Abilita aggiornamenti di sicurezza non presidiati
dpkg-reconfigure --priority=low unattended-upgrades || true

# ---------------------------------------------------------------------------
# 2. Swap (2 GiB — rete di sicurezza per burst di memoria)
# ---------------------------------------------------------------------------
if ! swapon --show | grep -q '/swapfile'; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
  echo "Swap 2 GiB attivato."
fi

# ---------------------------------------------------------------------------
# 3. Docker CE + Compose plugin
# ---------------------------------------------------------------------------
install -m 0755 -d /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
fi

source /etc/os-release
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update
apt-get install -y --no-install-recommends docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable --now docker
systemctl enable --now pcscd || true

# ---------------------------------------------------------------------------
# 4. Directory runtime
# ---------------------------------------------------------------------------
mkdir -p \
  /opt/iusentra/repo \
  /opt/iusentra/data \
  /opt/iusentra/backups \
  /opt/iusentra/caddy_data \
  /opt/iusentra/caddy_config \
  /opt/iusentra/import \
  /var/log/iusentra
chmod 750 \
  /opt/iusentra \
  /opt/iusentra/data \
  /opt/iusentra/backups \
  /opt/iusentra/import

# ---------------------------------------------------------------------------
# 5. Firewall UFW
# ---------------------------------------------------------------------------
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# ---------------------------------------------------------------------------
# 6. Fail2ban — protezione SSH e brute-force HTTP
# ---------------------------------------------------------------------------
cat > /etc/fail2ban/jail.d/iusentra.conf << 'EOF'
[sshd]
enabled  = true
maxretry = 5
bantime  = 3600
findtime = 600

[caddy-http-auth]
enabled  = false
port     = http,https
logpath  = /var/log/iusentra/access.log
maxretry = 10
bantime  = 1800
findtime = 300
EOF
systemctl enable --now fail2ban

# ---------------------------------------------------------------------------
# 7. Logrotate per log applicativi
# ---------------------------------------------------------------------------
cat > /etc/logrotate.d/iusentra << 'EOF'
/var/log/iusentra/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root root
}
EOF

echo ""
echo "Bootstrap Hetzner completato."
echo ""
echo "Prossimi passi:"
echo "  1. cp /opt/iusentra/repo/deploy/hetzner/env.hetzner.example /opt/iusentra/.env.hetzner"
echo "  2. nano /opt/iusentra/.env.hetzner  # compilare dominio, secrets, email ACME"
echo "  3. cd /opt/iusentra/repo && bash deploy/hetzner/deploy.sh"
