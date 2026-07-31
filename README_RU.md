# Telegram Business Follow-up

Автоматический, законный follow-up для Telegram Business через официальный Bot API и `business_connection_id`. Проект не использует userbot, вход по номеру, Telethon, Pyrogram или историю пользовательской сессии.

## Существенное ограничение Telegram

Bot API не позволяет боту выгружать существующую историческую переписку. Бот получает только `business_connection` и новые `business_message` updates после подключения к Business-аккаунту. Поэтому первоначальная база формируется только из таких разрешённых личных диалогов, а не из скрытого импорта истории. Для старых диалогов понадобится дождаться нового сообщения/события, доступного через Business Connection.

## Быстрый запуск

1. Создайте бота через BotFather, подключите его как Telegram Business bot и включите доступ к личным чатам.
2. Скопируйте `.env.example` в `.env`; заполните `BOT_TOKEN`, `ADMIN_IDS` и `DATABASE_URL`. Оставьте `AUTOMATION_ENABLED=false` до проверки.
3. Запустите PostgreSQL и выполните `alembic upgrade head`.
4. Запустите `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
5. Проверьте `/health`, затем отправьте Business-аккаунту тестовое сообщение. Клиент появится после `business_message` update.

## Поведение автоматизации

В 10:00 Europe/Moscow создаётся случайная очередь до `DAILY_LIMIT` (обычно 10–15). Сервис перед каждой отправкой повторяет проверку, отправляет только с 10:00 до 19:00 и разносит сообщения на 20–45 минут. Срабатывание стоп-слов или ответ после follow-up немедленно отменяет будущую очередь. `AUTOMATION_ENABLED=false` запрещает и создание очереди, и отправку.

Команды доступны только пользователям из `ADMIN_IDS`: `/status`, `/today`, `/queue`, `/clients`, `/inactive 7`, `/exclude USER_ID`, `/include USER_ID`, `/pause USER_ID`, `/resume USER_ID`, `/pause_all`, `/resume_all`, `/stop_all`, `/stats`, `/scripts`, `/set_limit 15`, `/set_days 30`.

`/set_limit` и `/set_days` применяются до перезапуска; для постоянной конфигурации меняйте Railway variables.

## Railway

Создайте PostgreSQL plugin, задайте переменные окружения из `.env.example` и deploy из репозитория. `railway.toml` использует Dockerfile. Контейнер применяет миграции перед запуском. Поскольку используется long polling, нужен один экземпляр сервиса.

## Проверка

`pytest -q` запускает тесты фильтров и времени планировщика. `alembic upgrade head` проверяет миграцию на PostgreSQL. `docker build -t telegram-followup .` проверяет контейнер.

Для локального запуска с Docker Compose: скопируйте `.env.example` в `.env`, заполните `BOT_TOKEN` и `ADMIN_IDS`, затем выполните `docker compose up --build`. Compose сам поднимет PostgreSQL и применит миграции.
