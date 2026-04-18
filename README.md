# Velocity Claw

<div align="center">
  <img src="assets/velocity_claw_falcon.png" alt="Velocity Claw - Falcon" width="400"/>
</div>

Velocity Claw — это production-ready AI-агент с архитектурой для реальной работы на Windows, Linux и сервере/VPS. Он ориентирован на высокую автономность, разбиение сложных задач на этапы, выполнение операций с файлами, кодом, API, Git и shell.

## Ключевые возможности

- Модульная архитектура: `core`, `planner`, `executor`, `models`, `tools`, `memory`, `telegram_bot`, `api`, `config`, `logs`, `prompts`, `security`
- Поддержка OpenAI, OpenRouter, Anthropic, Gemini и локальных моделей через Ollama
- Telegram-бот для управления задачами
- REST API на FastAPI
- Локальный CLI
- Память задач и предпочтений через SQLite
- Безопасные режимы `safe mode`, `dev mode`, `trusted mode`
- Инструменты: файловая система, shell, Python execution, Git, HTTP, кодовый поиск, JSON/YAML, Markdown, Docker

## Установка

### Windows PowerShell

```powershell
cd C:\Users\gavar\VelocityClaw
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

### Linux / bash

```bash
cd ~/VelocityClaw
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Настройка API ключей

Заполните `.env`:

- `TELEGRAM_TOKEN` — токен бота Telegram
- `TELEGRAM_CHAT_ID` — ваш Telegram chat id для контроля доступа
- `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`
- `OLLAMA_URL` — endpoint локального сервера Ollama, если есть

## Запуск

### CLI

```bash
python cli.py --task "Анализ проекта и рефакторинг основных модулей"
```

### FastAPI

```bash
python cli.py --server
```

API доступен на `http://127.0.0.1:8000`

### Telegram

```bash
python cli.py --telegram
```

## Docker

```bash
docker build -t velocity-claw .
docker run --env-file .env -p 8000:8000 velocity-claw
```

## Telegram-бот: команды

- `/start` — запуск бота
- `/help` — инструкция
- `/status` — текущее состояние
- `/model` — текущая модель/настройки
- `/reset` — сброс памяти текущей задачи
- `/task` — выполнить задачу
- `/plan` — показать план задачи
- `/logs` — показать последние логи
- `/stop` — остановить выполнение

## Структура проекта

- `velocity_claw/config` — конфигурация через `.env`
- `velocity_claw/core` — ядро агентной логики
- `velocity_claw/planner` — декомпозиция целей
- `velocity_claw/executor` — исполнение и проверка шагов
- `velocity_claw/models` — роутинг и интеграции моделей
- `velocity_claw/tools` — системные инструменты
- `velocity_claw/memory` — краткосрочная и долговременная память
- `velocity_claw/telegram_bot` — Telegram интерфейс
- `velocity_claw/api` — REST API
- `velocity_claw/security` — контроль доступа и подтверждений

## Примеры запросов к API

```bash
curl -X POST http://127.0.0.1:8000/task -H "Content-Type: application/json" -d '{"task": "Проанализируй текущую структуру проекта и предложи улучшения"}'
```

## Тесты

```bash
python -m unittest discover tests
```
