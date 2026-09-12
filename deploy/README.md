# Развёртывание на Yandex Cloud

Приложение — один процесс на одном порту: бэкенд отдаёт и API, и интерфейс.
Поэтому хватает самой маленькой виртуальной машины, база лежит в файле SQLite.

Разворачивание идёт через cloud-init: машина настраивает себя сама при первой
загрузке. Заходить по SSH не требуется.

## Что понадобится

- аккаунт в Yandex Cloud с привязанным платёжным аккаунтом;
- установленная утилита `yc`;
- пара SSH-ключей (нужна только на случай, если захотите зайти на машину руками).

## Шаг 1. Поставить и настроить `yc`

```bash
curl -sSL https://storage.yandexcloud.net/yandexcloud-yc/install.sh | bash
exec -l $SHELL
yc init
```

`yc init` откроет браузер, попросит выбрать облако, каталог и зону доступности.
Для Москвы подойдёт `ru-central1-a`.

## Шаг 2. Подготовить ключи

```bash
# SSH-ключ, если его ещё нет
ssh-keygen -t ed25519 -C "shorthack" -f ~/.ssh/id_ed25519 -N ""
```

Откройте `deploy/cloud-init.yaml` и впишите в блок `env.sh` адрес репозитория
и ключ языковой модели. Если ключа ещё нет, оставьте `LLM_PROVIDER=mock`:
приложение поднимется и будет работать в демонстрационном режиме, а переключить
его можно позже одной правкой файла и перезапуском службы.

## Шаг 3. Создать машину

```bash
yc compute instance create \
  --name supportpilot \
  --zone ru-central1-a \
  --platform standard-v3 \
  --cores 2 --memory 4 --core-fraction 50 \
  --create-boot-disk image-folder-id=standard-images,image-family=ubuntu-2404-lts,size=20,type=network-ssd \
  --network-interface subnet-name=default-ru-central1-a,nat-ip-version=ipv4 \
  --metadata-from-file user-data=deploy/cloud-init.yaml \
  --ssh-key ~/.ssh/id_ed25519.pub
```

Команда выведет публичный адрес в поле `one_to_one_nat.address`.

Настройка занимает пять–семь минут: машина ставит Node, собирает интерфейс,
поднимает службу и разбирает демонстрационную очередь. Пока она идёт, по адресу
может отвечать ошибка шлюза — это нормально.

## Шаг 4. Проверить

```bash
IP=<адрес из вывода>
curl http://$IP/api/health
open http://$IP
```

Ответ `/api/health` покажет, на чём работает помощник и в каком режиме поиск.

## Если что-то пошло не так

```bash
ssh pilot@$IP
sudo tail -100 /var/log/supportpilot-install.log   # лог установки
sudo systemctl status supportpilot                 # состояние службы
sudo journalctl -u supportpilot -n 100 --no-pager   # лог приложения
```

## Подключить ключ модели после развёртывания

```bash
ssh pilot@$IP
sudo nano /opt/supportpilot/app/backend/.env       # вписать LLM_PROVIDER, LLM_API_KEY, LLM_BASE_URL
sudo systemctl restart supportpilot
curl -X POST http://127.0.0.1:8000/api/reindex     # пересобрать индекс с векторами
```

## Обновить до свежей версии

```bash
ssh pilot@$IP
cd /opt/supportpilot/app && sudo -u pilot git pull
cd frontend && sudo -u pilot npm ci && sudo -u pilot npm run build
sudo systemctl restart supportpilot
```

## Сколько это стоит

Машина на 2 ядрах с долей 50 процентов, 4 ГБ памяти и диском 20 ГБ обходится
примерно в сто рублей в сутки. После защиты машину лучше удалить:

```bash
yc compute instance delete supportpilot
```

## Если нужен домен и HTTPS

Проще всего заменить nginx на Caddy: он получает сертификат сам.
В `cloud-init.yaml` вместо пакета `nginx` поставьте `caddy`, а конфигурацию
сведите к двум строкам:

```
ваш-домен.ru {
  reverse_proxy 127.0.0.1:8000
}
```

Для защиты это не обязательно: жюри открывает прототип по адресу с портом 80.
