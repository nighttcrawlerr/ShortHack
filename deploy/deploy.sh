#!/usr/bin/env bash
#
# Разворачивает SaluteAgent на новой машине в Yandex Cloud.
#
# Ключ модели берётся из backend/.env и попадает в конфигурацию машины
# в кодировке base64. В репозиторий он не записывается и в аргументах
# команды не светится.
#
# Перед первым запуском:
#   yc init
#   ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="${NAME:-saluteagent}"
ZONE="${ZONE:-ru-central1-a}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519.pub}"

YC="$(command -v yc || echo "$HOME/yandex-cloud/bin/yc")"
[ -x "$YC" ] || { echo "Не найдена утилита yc. Установите её и выполните yc init."; exit 1; }

"$YC" config list >/dev/null 2>&1 || { echo "yc не настроен. Выполните: yc init"; exit 1; }
[ -f "$SSH_KEY" ] || { echo "Нет ключа $SSH_KEY. Создайте: ssh-keygen -t ed25519 -f ${SSH_KEY%.pub} -N \"\""; exit 1; }

USERDATA="$(mktemp -t saluteagent-cloudinit)"
trap 'rm -f "$USERDATA"' EXIT

python3 "$ROOT/deploy/make_userdata.py" \
  --env "$ROOT/backend/.env" \
  --ssh-key "$SSH_KEY" \
  --out "$USERDATA"

# В свежем каталоге сети может не быть: создаём, если её нет
if ! "$YC" vpc network get --name default >/dev/null 2>&1; then
  echo "Создаю сеть default"
  "$YC" vpc network create --name default --description "SaluteAgent" >/dev/null
fi
if ! "$YC" vpc subnet get --name "default-$ZONE" >/dev/null 2>&1; then
  echo "Создаю подсеть default-$ZONE"
  "$YC" vpc subnet create --name "default-$ZONE" --network-name default \
    --zone "$ZONE" --range 10.128.0.0/24 >/dev/null
fi

if "$YC" compute instance get --name "$NAME" >/dev/null 2>&1; then
  echo "Машина $NAME уже существует. Удалите её или задайте другое имя через NAME=."
  exit 1
fi

echo "Создаю машину $NAME в зоне $ZONE."
"$YC" compute instance create \
  --name "$NAME" \
  --zone "$ZONE" \
  --platform standard-v3 \
  --cores 2 --memory 4 --core-fraction 50 \
  --create-boot-disk image-folder-id=standard-images,image-family=ubuntu-2404-lts,size=20,type=network-ssd \
  --network-interface subnet-name="default-$ZONE",nat-ip-version=ipv4 \
  --metadata-from-file user-data="$USERDATA" \
  --format json > /tmp/saluteagent-instance.json

IP="$(python3 -c "
import json
d = json.load(open('/tmp/saluteagent-instance.json'))
print(d['network_interfaces'][0]['primary_v4_address']['one_to_one_nat']['address'])
")"

echo
echo "Машина создана. Адрес: http://$IP"
echo "Настройка занимает пять-семь минут, пока может отвечать ошибка шлюза."
echo
echo "Дождаться готовности:"
echo "  until curl -sf http://$IP/api/health; do sleep 15; done"
echo
echo "Лог установки:"
echo "  ssh pilot@$IP 'sudo tail -50 /var/log/saluteagent-install.log'"
echo
echo "Удалить после защиты:"
echo "  $YC compute instance delete $NAME"
