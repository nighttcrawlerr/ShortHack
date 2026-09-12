#!/usr/bin/env bash
# Разворачивает приложение на чистой машине. Запускается один раз при первой
# загрузке. Значения берутся из /opt/saluteagent/env.sh.
set -euo pipefail

source /opt/saluteagent/env.sh

export DEBIAN_FRONTEND=noninteractive

# Node нужен один раз, чтобы собрать интерфейс
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt-get install -y nodejs

rm -rf /opt/saluteagent/app
git clone --depth 1 "$GIT_REPO" /opt/saluteagent/app

cd /opt/saluteagent/app/frontend
npm ci --no-audit --no-fund
npm run build

cd /opt/saluteagent/app/backend
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# Настройки приложения собираются из env.sh
{
  echo "LLM_PROVIDER=$LLM_PROVIDER"
  echo "LLM_BASE_URL=$LLM_BASE_URL"
  echo "LLM_API_KEY=$LLM_API_KEY"
  echo "LLM_FOLDER_ID=$LLM_FOLDER_ID"
  echo "LLM_MODEL=$LLM_MODEL"
  echo "LLM_TOOLS=$LLM_TOOLS"
  echo "LLM_TIMEOUT=$LLM_TIMEOUT"
  echo "LLM_FALLBACK_TO_MOCK=$LLM_FALLBACK_TO_MOCK"
  echo "EMBEDDINGS_PROVIDER=$EMBEDDINGS_PROVIDER"
  echo "VERIFY_WITH_MODEL=$VERIFY_WITH_MODEL"
  echo "AUTO_SEND=$AUTO_SEND"
} > /opt/saluteagent/app/backend/.env
chmod 600 /opt/saluteagent/app/backend/.env

chown -R pilot:pilot /opt/saluteagent

ln -sf /etc/nginx/sites-available/saluteagent /etc/nginx/sites-enabled/saluteagent
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

systemctl daemon-reload
systemctl enable --now saluteagent

# Ждём, пока поднимется, и наполняем очередь разобранными обращениями,
# чтобы приложение открывалось на готовых данных
for _ in $(seq 1 40); do
  curl -sf http://127.0.0.1:8000/api/health >/dev/null && break
  sleep 3
done
curl -sf -m 600 -X POST http://127.0.0.1:8000/api/messages/analyze-all >/dev/null || true

echo "УСТАНОВКА ЗАВЕРШЕНА"
