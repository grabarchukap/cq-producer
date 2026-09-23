# Развёртывание на сервере (Docker + Cloudflare Tunnel, режим webhook)

Схема: Ubuntu-сервер с Docker, `cloudflared` работает в своём контейнере. Бот и `cloudflared`
сидят в одной docker-сети, туннель проксирует `https://<хост>` → `http://cq-producer:8443`.
Порт бота наружу не публикуется — ни в интернет, ни в локалку.

Команды на сервере выполняются по SSH, команды «на ПК» — в PowerShell на Windows.

---

## 0. Что должно быть готово

- SSH-доступ к серверу, `docker` и `docker compose` на нём.
- Контейнер `cloudflared` с рабочим туннелем.
- Хостнейм в Cloudflare под этого бота, например `cq.example.com`.
- Ключи: токен бота, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`.
- Для выгрузки кейсов: `token.json` (получен через `auth_google.py` на ПК) и ID папки Google Drive.
- Все текущие правки закоммичены и запушены в репозиторий.

## 1. Общая сеть с cloudflared (один раз на сервер)

Бот ищет docker-сеть с именем из `TUNNEL_NETWORK` (по умолчанию `tgbots`) и сам её не создаёт.

Посмотреть, есть ли уже сеть, в которой живёт `cloudflared`:

```bash
docker ps --format '{{.Names}}' | grep -i cloudflared         # имя контейнера
docker inspect <имя-контейнера> --format '{{json .NetworkSettings.Networks}}'
```

- **Сеть уже есть** (например, туда подключены другие боты) — запомни её имя, пропиши его
  в `TUNNEL_NETWORK` на шаге 3.
- **Сети нет** — создай и подключи к ней `cloudflared`:

  ```bash
  docker network create tgbots
  docker network connect tgbots <имя-контейнера-cloudflared>
  ```

  Если `cloudflared` запущен через свой `docker-compose.yml`, лучше прописать сеть там,
  иначе после пересоздания контейнера подключение пропадёт:

  ```yaml
  services:
    cloudflared:
      # ...
      networks: [tgbots]
  networks:
    tgbots:
      external: true
  ```

## 2. Код

```bash
cd ~
git clone <url-репозитория> cq-producer
cd cq-producer
```

Папка данных — всё, что бот пишет, лежит здесь. Внутри контейнера бот работает как uid 1000:

```bash
mkdir data
sudo chown 1000:1000 data
sudo chmod 700 data
```

## 3. `.env`

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

Что заполнить:

| Переменная | Значение |
|---|---|
| `TELEGRAM_BOT_TOKEN` | токен от @BotFather |
| `ANTHROPIC_API_KEY` | ключ Anthropic |
| `GROQ_API_KEY` | ключ Groq — без него голосовые не распознаются |
| `ADMIN_PASSWORD` | длинный случайный: `openssl rand -base64 18` |
| `DEV_MODE` | `false` |
| `WEBHOOK_URL` | `https://cq.example.com` — хост туннеля, **без** слеша в конце |
| `WEBHOOK_PORT` | `8443` (порт внутри контейнера, наружу не публикуется) |
| `WEBHOOK_SECRET_TOKEN` | `openssl rand -hex 32` — обязательно, URL публичный |
| `TUNNEL_NETWORK` | имя сети из шага 1 |
| `DATA_DIR` | оставить пустым — compose сам ставит `/data` |
| `GOOGLE_TOKEN_FILE` | оставить пустым — будет `/data/token.json` |
| `GOOGLE_DRIVE_FOLDER_ID` | ID папки из её URL `drive.google.com/drive/folders/<ID>` |

## 4. Перенос `token.json`

В файле лежит refresh-токен и client secret — это доступ к твоему Google Drive.
Переносим только по SSH: не через Telegram, почту или облачные диски.

**На ПК** (в PowerShell, `scp` встроен в Windows):

```powershell
scp "C:\путь\к\token.json" user@server:~/cq-producer/data/token.json
```

**На сервере:**

```bash
sudo chown 1000:1000 ~/cq-producer/data/token.json
sudo chmod 600 ~/cq-producer/data/token.json
```

Владелец именно 1000: бот сам перезаписывает этот файл при обновлении токена (примерно раз в час),
и без прав на запись выгрузка кейсов сломается через час после старта.

После переноса удали лишние копии `token.json` на ПК, если они валяются где-то кроме папки проекта.
В git файл не попадёт: `token.json` и `data/` в `.gitignore`.

## 5. Сборка и запуск

```bash
cd ~/cq-producer
docker compose up -d --build
docker compose logs -f bot
```

В логах должно быть `Data directory ready: /data`, `Database ready: /data/posts.db`
и `Starting webhook on 0.0.0.0:8443`. Выход из логов — `Ctrl+C`, бот продолжит работать.

При первом старте в `data/` появятся `posts.db`, `authors/`, `questions.json`, `draft_prompt.txt`.

## 6. Маршрут в туннеле

Туннель должен вести хост бота на `http://cq-producer:8443` (протокол **HTTP**, не HTTPS —
TLS снимает Cloudflare).

- **Туннель управляется из дашборда** (Zero Trust → Networks → Tunnels → твой туннель →
  Public Hostname → Add): хост `cq.example.com`, Service — `HTTP`, URL — `cq-producer:8443`.
- **Туннель на `config.yml`**: добавить правило **выше** последнего catch-all и перезапустить `cloudflared`:

  ```yaml
  ingress:
    - hostname: cq.example.com
      service: http://cq-producer:8443
    # ... остальные правила ...
    - service: http_status:404
  ```

## 7. Проверка вебхука

```bash
TOKEN=$(grep '^TELEGRAM_BOT_TOKEN=' .env | cut -d= -f2-)
curl -s "https://api.telegram.org/bot$TOKEN/getWebhookInfo"; echo
```

Ожидаем: `url` — твой хост с токеном в пути, `pending_update_count` близко к нулю,
и **нет** поля `last_error_message`. Токен при этом не попадает в историю команд.

Если ошибка есть:

| `last_error_message` | Причина |
|---|---|
| `Wrong response from the webhook: 502 Bad Gateway` | туннель не видит бота: не та сеть (шаг 1) или не тот адрес в маршруте (шаг 6) |
| `Wrong response from the webhook: 404 Not Found` | маршрут в туннеле не создан или стоит ниже catch-all |
| `Wrong response from the webhook: 403 Forbidden` | не совпал `WEBHOOK_SECRET_TOKEN` — после правки `.env` нужен `docker compose up -d` |
| `SSL error ...` | в маршруте указан `https://` вместо `http://` |

## 8. Первый вход

База пустая, поэтому доступа к боту нет ни у кого, включая тебя.

1. Узнай свой Telegram ID — например, у @userinfobot.
2. В боте: кнопка «⚙️ Админка» или `/admin` → пароль из `ADMIN_PASSWORD`.
3. В управлении пользователями добавь свой ID в whitelist.
4. В разделе получателей уведомлений добавь тех, кому приходят новые кейсы.
5. Проверь: `/start` → пост из текста, пост из голосового, короткое интервью по кейсу →
   ссылка на документ в уведомлении.

После 5 неверных паролей админка блокируется для этого пользователя на 15 минут.

## Обновление

```bash
cd ~/cq-producer
git pull
docker compose up -d --build
```

Данные в `data/` не трогаются: профили, вопросы и промпт, изменённые из админки, сохраняются.
Новые стартовые профили или вопросы из репозитория в `data/` сами **не** попадут — туда копируется
только то, чего там ещё нет.

## Бэкап

Всё состояние бота — папка `data/`. SQLite в режиме WAL, поэтому копируем на остановленном боте:

```bash
cd ~/cq-producer
docker compose stop
sudo tar czf ~/cq-producer-backup-$(date +%F).tar.gz data
docker compose start
```

В архиве лежит `token.json` — храни его так же, как сам токен.

## Если что-то не так

- **`network tgbots declared as external, but could not be found`** — сеть не создана
  или имя в `TUNNEL_NETWORK` другое (шаг 1).
- **`Permission denied` на `/data`** — владелец папки не 1000: `sudo chown -R 1000:1000 data`.
- **`Required environment variable ... is not set`** — не заполнена переменная в `.env`.
- **На голосовое отвечает «Распознавание голосовых не настроено»** — нет `GROQ_API_KEY`.
- **Кейсы висят в «Зависших задачах»** — смотри `docker compose logs bot | grep -i export`:
  обычно это `token.json` (нет файла или прав) или пустой `GOOGLE_DRIVE_FOLDER_ID`.
