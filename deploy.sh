#!/usr/bin/env bash
# Деплой Agent Scout на Digital Ocean (Ubuntu 22.04+)
# Трафик агента идёт через SOCKS5 прокси → Selectel (Москва)
#
# Запуск: scp deploy.sh root@<DO_IP>:~ && ssh root@<DO_IP> bash deploy.sh

set -euo pipefail

SELECTEL_IP="111.88.126.97"
APP_DIR="/opt/agent-scout"

echo "=== Agent Scout: Деплой на Digital Ocean ==="

# 1. Системные зависимости
echo "[1/7] Установка системных пакетов..."
apt-get update -qq
apt-get install -y -qq python3.11 python3.11-venv python3-pip git autossh \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libdbus-1-3 libxkbcommon0 libatspi2.0-0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libxshmfence1 > /dev/null 2>&1

# 2. SSH-ключ для туннеля к Selectel (если ещё нет)
echo "[2/7] Настройка SSH-ключа для Selectel..."
if [ ! -f /root/.ssh/id_ed25519 ]; then
    ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519 -N "" -q
    echo ""
    echo "  !! ВАЖНО: скопируйте публичный ключ на Selectel:"
    echo "  ssh-copy-id -i /root/.ssh/id_ed25519.pub root@${SELECTEL_IP}"
    echo "  (или вручную добавьте в /root/.ssh/authorized_keys на Selectel)"
    echo ""
    echo "  После этого запустите deploy.sh ещё раз."
    cat /root/.ssh/id_ed25519.pub
    exit 1
fi

# Проверяем доступ к Selectel
if ! ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 root@${SELECTEL_IP} "echo ok" > /dev/null 2>&1; then
    echo "  !! Нет SSH-доступа к Selectel (${SELECTEL_IP})"
    echo "  Скопируйте ключ: ssh-copy-id root@${SELECTEL_IP}"
    exit 1
fi
echo "  >> SSH к Selectel работает"

# 3. Клонирование / обновление репозитория
echo "[3/7] Настройка репозитория в ${APP_DIR}..."
if [ -d "$APP_DIR" ]; then
    cd "$APP_DIR"
    git pull origin claude/web-scraper-agent-eown9
else
    git clone -b claude/web-scraper-agent-eown9 \
        https://github.com/andrushasueta-ai/agent-scout.git "$APP_DIR"
    cd "$APP_DIR"
fi

# 4. Python venv и зависимости
echo "[4/7] Установка Python-зависимостей..."
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -e ".[dev]" -q

# 5. Playwright и Chromium
echo "[5/7] Установка Playwright Chromium..."
playwright install chromium
playwright install-deps chromium 2>/dev/null || true

# 6. Файл .env (API-ключ)
echo "[6/7] Настройка .env..."
if [ ! -f .env ]; then
    echo "ANTHROPIC_API_KEY=ВАШ_КЛЮЧ_СЮДА" > .env
    echo "  >> Отредактируйте .env: nano ${APP_DIR}/.env"
else
    echo "  >> .env уже существует, пропускаю"
fi

# 7. Создание директорий + systemd-сервисы
echo "[7/7] Настройка systemd-сервисов..."
mkdir -p data/sessions

# Сервис SSH-туннеля (autossh — автоматически переподключается)
cat > /etc/systemd/system/socks-tunnel.service << TUNNEL_EOF
[Unit]
Description=SOCKS5 SSH-туннель к Selectel (Москва)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/autossh -M 0 -N -D 1080 -o "ServerAliveInterval=30" -o "ServerAliveCountMax=3" -o "StrictHostKeyChecking=no" -o "ExitOnForwardFailure=yes" root@${SELECTEL_IP}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
TUNNEL_EOF

# Сервис Agent Scout
cp ${APP_DIR}/agent-scout.service /etc/systemd/system/

systemctl daemon-reload
systemctl enable socks-tunnel
systemctl start socks-tunnel

# Ждём пока туннель поднимется
sleep 3
if curl -s --socks5-hostname localhost:1080 ifconfig.me 2>/dev/null | grep -q .; then
    PROXY_IP=$(curl -s --socks5-hostname localhost:1080 ifconfig.me)
    echo "  >> SOCKS5 туннель работает, IP: ${PROXY_IP}"
else
    echo "  !! Туннель не поднялся, проверьте: journalctl -u socks-tunnel"
fi

echo ""
echo "=== Готово! ==="
echo ""
echo "Следующие шаги:"
echo "  1. Отредактируйте API-ключ:  nano ${APP_DIR}/.env"
echo "  2. Тест:  cd ${APP_DIR} && source venv/bin/activate && agent-scout status"
echo "  3. Запуск вручную:  agent-scout scrape -p avito -n 'механизированная штукатурка' -l 'Москва' --limit 3"
echo "  4. Автозапуск:  systemctl enable --now agent-scout"
echo ""
echo "Мониторинг:"
echo "  journalctl -u agent-scout -f      # логи агента"
echo "  journalctl -u socks-tunnel -f     # логи туннеля"
echo "  curl --socks5 localhost:1080 ifconfig.me  # проверка IP"
