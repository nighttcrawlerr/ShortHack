# Развёртывание на Yandex Cloud

Приложение — один процесс на одном порту: бэкенд отдаёт и API, и интерфейс.
Поэтому хватает самой маленькой виртуальной машины, база лежит в файле SQLite.

Разворачивание идёт через cloud-init: машина настраивает себя сама при первой
загрузке. Заходить по SSH не требуется.

## Что уже готово

- утилита `yc` установлена в `~/yandex-cloud/bin`;
- SSH-ключ создан в `~/.ssh/id_ed25519`;
- скрипт `deploy/deploy.sh` собирает конфигурацию машины и создаёт её.

Понадобится только аккаунт Yandex Cloud с привязанным платёжным аккаунтом.

## Шаг 1. Войти в Yandex Cloud

Утилита `yc` уже установлена в `~/yandex-cloud/bin`. Остался вход:

```bash
~/yandex-cloud/bin/yc init
```

Команда откроет браузер, попросит войти и выбрать облако, каталог и зону.
Для Москвы подойдёт `ru-central1-a`.

Это единственный шаг, который нельзя выполнить за вас: ключ от моделей
даёт доступ только к AI Studio, управлять машинами им нельзя.

## Шаг 2. Развернуть

```bash
./deploy/deploy.sh
```

Скрипт сам подставит ключ модели из `backend/.env` в конфигурацию машины,
создаст её и выведет адрес. Ключ при этом не попадает ни в репозиторий,
ни в аргументы команды.

Переменные, которые можно переопределить:

```bash
NAME=saluteagent ZONE=ru-central1-a ./deploy/deploy.sh
```

## Шаг 3. Дождаться

Настройка занимает пять–семь минут: машина ставит Node, собирает интерфейс,
поднимает службу и разбирает демонстрационную очередь. Пока она идёт, адрес
отвечает ошибкой шлюза — это нормально.

```bash
until curl -sf http://АДРЕС/api/health; do sleep 15; done
```

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
sudo tail -100 /var/log/saluteagent-install.log   # лог установки
sudo systemctl status saluteagent                 # состояние службы
sudo journalctl -u saluteagent -n 100 --no-pager   # лог приложения
```

## Подключить ключ модели после развёртывания

```bash
ssh pilot@$IP
sudo nano /opt/saluteagent/app/backend/.env       # вписать LLM_PROVIDER, LLM_API_KEY, LLM_BASE_URL
sudo systemctl restart saluteagent
curl -X POST http://127.0.0.1:8000/api/reindex     # пересобрать индекс с векторами
```

## Обновить до свежей версии

```bash
ssh pilot@$IP
cd /opt/saluteagent/app && sudo -u pilot git pull
cd frontend && sudo -u pilot npm ci && sudo -u pilot npm run build
sudo systemctl restart saluteagent
```

## Сколько это стоит

Машина на 2 ядрах с долей 50 процентов, 4 ГБ памяти и диском 20 ГБ обходится
примерно в сто рублей в сутки. После защиты машину лучше удалить:

```bash
yc compute instance delete saluteagent
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
