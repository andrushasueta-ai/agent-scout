#!/usr/bin/env bash
# Деплой Agent Scout на VPS (Ubuntu 22.04+)
# Запуск: ssh root@111.88.126.97 'bash -s' < deploy.sh

set -euo pipefail

echo "=== Agent Scout: Деплой на VPS ==="

# 1. Системные зависимости
echo "[1/6] Установка системных пакетов..."
apt-get update -qq
apt-get install -y -qq python3.11 python3.11-venv python3-pip git \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libdbus-1-3 libxkbcommon0 libatspi2.0-0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libxshmfence1 > /dev/null 2>&1

# 2. Клонирование / обновление репозитория
APP_DIR="/opt/agent-scout"
echo "[2/6] Настройка репозитория в ${APP_DIR}..."
if [ -d "$APP_DIR" ]; then
    cd "$APP_DIR"
    git pull origin claude/web-scraper-agent-eown9
else
    git clone -b claude/web-scraper-agent-eown9 \
        https://github.com/andrushasueta-ai/agent-scout.git "$APP_DIR"
    cd "$APP_DIR"
fi

# 3. Python venv и зависимости
echo "[3/6] Установка Python-зависимостей..."
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -e ".[dev]" -q

# 4. Playwright и Chromium
echo "[4/6] Установка Playwright Chromium..."
playwright install chromium
playwright install-deps chromium 2>/dev/null || true

# 5. Файл .env (API-ключ)
echo "[5/6] Настройка .env..."
if [ ! -f .env ]; then
    echo "ANTHROPIC_API_KEY=ВАШ_КЛЮЧ_СЮДА" > .env
    echo "  >> Отредактируйте .env: nano ${APP_DIR}/.env"
else
    echo "  >> .env уже существует, пропускаю"
fi

# 6. Создание директорий для данных
echo "[6/6] Создание директорий..."
mkdir -p data/sessions

echo ""
echo "=== Готово! ==="
echo ""
echo "Следующие шаги:"
echo "  1. Отредактируйте API-ключ:  nano ${APP_DIR}/.env"
echo "  2. Настройте конфиг:         nano ${APP_DIR}/config.yaml"
echo "  3. Тест:                     cd ${APP_DIR} && source venv/bin/activate && agent-scout status"
echo "  4. Запуск:                   agent-scout run"
echo ""
echo "Для автозапуска как сервис:"
echo "  cp ${APP_DIR}/agent-scout.service /etc/systemd/system/"
echo "  systemctl daemon-reload"
echo "  systemctl enable --now agent-scout"
