#!/usr/bin/env bash
#
# Разворачивает SupportPilot на новой машине в Yandex Cloud.
#
# Ключ модели берётся из backend/.env и подставляется в конфигурацию машины
# на лету. В репозиторий он не попадает и в аргументах команды не светится.
#
# Перед первым запуском:
#   yc init
#   ssh-keygen -t ed25519 -C shorthack -f ~/.ssh/id_ed25519 -N ""

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="${NAME:-supportpilot}"
ZONE="${ZONE:-ru-central1-a}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519.pub}"
REPO="${REPO:-https://github.com/nighttcrawlerr/ShortHack}"

YC="$(command -v yc || echo "$HOME/yandex-cloud/bin/yc")"
[ -x "$YC" ] || { echo "Не найдена утилита yc. Установите её и выполните yc init."; exit 1; }

"$YC" config list >/dev/null 2>&1 || { echo "yc не настроен. Выполните: yc init"; exit 1; }
[ -f "$SSH_KEY" ] || { echo "Нет ключа $SSH_KEY. Создайте: ssh-keygen -t ed25519 -f ${SSH_KEY%.pub} -N \"\""; exit 1; }
[ -f "$ROOT/backend/.env" ] || { echo "Нет backend/.env с ключом модели."; exit 1; }

# Значения из локального .env
get() { grep -E "^$1=" "$ROOT/backend/.env" | head -1 | cut -d= -f2- ; }

LLM_PROVIDER="$(get LLM_PROVIDER)"
LLM_BASE_URL="$(get LLM_BASE_URL)"
LLM_API_KEY="$(get LLM_API_KEY)"
LLM_FOLDER_ID="$(get LLM_FOLDER_ID)"
LLM_MODEL="$(get LLM_MODEL)"

[ -n "$LLM_API_KEY" ] || echo "Внимание: ключ модели пуст, машина поднимется в демонстрационном режиме."

# Конфигурация машины собирается во временный файл и удаляется после запуска
USERDATA="$(mktemp -t supportpilot-cloudinit)"
trap 'rm -f "$USERDATA"' EXIT

python3 - "$ROOT/deploy/cloud-init.yaml" "$USERDATA" "$SSH_KEY" <<PY
import sys
src, dst, keyfile = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(src, encoding="utf-8").read()
text = text.replace("ПОДСТАВЛЯЕТСЯ_СКРИПТОМ", open(keyfile, encoding="utf-8").read().strip())
for key, value in {
    "GIT_REPO=https://github.com/nighttcrawlerr/ShortHack": "GIT_REPO=$REPO",
    "LLM_PROVIDER=yandex": "LLM_PROVIDER=$LLM_PROVIDER",
    "LLM_BASE_URL=https://llm.api.cloud.yandex.net/v1": "LLM_BASE_URL=$LLM_BASE_URL",
    "LLM_API_KEY=ВПИШИТЕ_КЛЮЧ": "LLM_API_KEY=$LLM_API_KEY",
    "LLM_FOLDER_ID=ВПИШИТЕ_ИДЕНТИФИКАТОР_КАТАЛОГА": "LLM_FOLDER_ID=$LLM_FOLDER_ID",
    "LLM_MODEL=yandexgpt-5-pro": "LLM_MODEL=$LLM_MODEL",
}.items():
    text = text.replace(key, value)
open(dst, "w", encoding="utf-8").write(text)
PY

# В свежем каталоге сети может не быть: создаём, если её нет
if ! "$YC" vpc network get --name default >/dev/null 2>&1; then
  echo "Создаю сеть default"
  "$YC" vpc network create --name default --description "SupportPilot" >/dev/null
fi
if ! "$YC" vpc subnet get --name "default-$ZONE" >/dev/null 2>&1; then
  echo "Создаю подсеть default-$ZONE"
  "$YC" vpc subnet create --name "default-$ZONE" --network-name default \
    --zone "$ZONE" --range 10.128.0.0/24 >/dev/null
fi

echo "Создаю машину $NAME в зоне $ZONE."
"$YC" compute instance create \
  --name "$NAME" \
  --zone "$ZONE" \
  --platform standard-v3 \
  --cores 2 --memory 4 --core-fraction 50 \
  --create-boot-disk image-folder-id=standard-images,image-family=ubuntu-2404-lts,size=20,type=network-ssd \
  --network-interface subnet-name=default-"$ZONE",nat-ip-version=ipv4 \
  --metadata-from-file user-data="$USERDATA" \
  --format json > /tmp/supportpilot-instance.json

IP="$(python3 -c "
import json
d = json.load(open('/tmp/supportpilot-instance.json'))
print(d['network_interfaces'][0]['primary_v4_address']['one_to_one_nat']['address'])
")"

echo
echo "Машина создана. Адрес: http://$IP"
echo "Настройка занимает пять–семь минут, пока может отвечать ошибка шлюза."
echo
echo "Проверить готовность:"
echo "  until curl -sf http://$IP/api/health; do sleep 15; done"
echo
echo "Посмотреть лог установки:"
echo "  ssh pilot@$IP 'sudo tail -50 /var/log/supportpilot-install.log'"
echo
echo "Удалить после защиты:"
echo "  $YC compute instance delete $NAME"
