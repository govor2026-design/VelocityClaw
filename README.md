# Velocity Claw

<div align="center">
  <img src="assets/velocity_claw_falcon.png" alt="Velocity Claw - Falcon" width="400"/>
</div>

Velocity Claw — AI-агент с модульной архитектурой для автономного выполнения задач: работа с файлами, shell-командами, Git, HTTP-запросами и LLM-провайдерами. Проект находится в стадии **strong foundation / MVP** — ядро работает и покрыто тестами, часть расширенных возможностей задокументирована как roadmap.

## Что реально реализовано

### Ядро агента
- `core/agent.py` — планирование → исполнение → сохранение в памяти
- `planner/planner.py` — LLM-разбивка задачи на шаги (JSON-план)
- `executor/executor.py` — исполнение шагов по типу инструмента
- `models/router.py` — маршрутизация запросов между LLM-провайдерами с fallback
- `memory/store.py` — SQLite: runs, steps, preferences, artifacts
- `security/policy.py` — профили доступа, валидация путей/команд/URL

### Инструменты (реально работают)
- `tools/fs.py` — чтение, запись, append, replace, поиск по содержимому, list_dir
- `tools/shell.py` — безопасный запуск shell-команд (allowlist: ls, pwd, echo, grep, find и др.)
- `tools/git.py` — безопасные git-команды (status, diff, add, commit, branch, log)
- `tools/http.py` — GET/POST с ограничением по размеру ответа и allowlist хостов
- `tools/docker.py` — валидация и запуск docker-команд (реализован, но не подключён к executor)
- `tools/editor.py` — вспомогательный редактор файлов

### Интерфейсы
- `api/server.py` — REST API на FastAPI (`/health`, `/task`, `/status`, `/reset`)
- `telegram_bot/bot.py` — Telegram-бот (python-telegram-bot)
- `cli.py` — CLI: `--task`, `--server`, `--telegram`, `--status`

### Режимы и конфигурация
- `safe_mode`, `dev_mode`, `trusted_mode` — флаги в Settings, читаются из `.env`
- `LOG_LEVEL` — управление уровнем логирования через env
- `logs/logger.py` — централизованный логгер без дублирования handlers

### Поддерживаемые LLM-провайдеры
- OpenAI, OpenRouter, Anthropic, Gemini, Ollama (с автоматическим fallback)

## Что пока только в документации / roadmap

Следующие возможности описаны в spec-документах, но **не реализованы в коде**:

| Возможность | Документ | Статус |
|---|---|---|
| Patch engine (автопатчинг кода) | `PATCH_ENGINE_SPEC.md` | spec only |
| Test runner (авторепорт по тестам) | `TEST_RUNNER_SPEC.md` | spec only |
| Symbol-aware navigation | `SYMBOL_NAV_SPEC.md` | spec only |
| Auto-fix loop | `AUTO_FIX_LOOP_SPEC.md` | spec only |
| Dashboard (веб-интерфейс) | `DASHBOARD_SPEC.md` | spec only |
| Approval workflow | `APPROVAL_WORKFLOW_SPEC.md` | spec only |
| Execution profiles | `EXECUTION_PROFILES_SPEC.md` | spec only |
| Python execution tool | — | не реализован |
| Кодовый поиск (symbol search) | — | только текстовый grep в `fs.search` |
| JSON/YAML tooling | — | только `fs.to_json` / `fs.write_json` |
| Markdown tooling | — | не реализован |

## Установка

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # заполните ключи
```

## Настройка `.env`

```
OPENAI_API_KEY=...
OPENROUTER_API_KEY=...
ANTHROPIC_API_KEY=...
GEMINI_API_KEY=...
OLLAMA_URL=http://127.0.0.1:11434

TELEGRAM_TOKEN=...
TELEGRAM_CHAT_ID=...

LOG_LEVEL=INFO
SAFE_MODE=true
MEMORY_ENABLED=true
WORKSPACE_ROOT=.
```

## Запуск

### CLI — выполнить задачу
```bash
python cli.py --task "Проанализируй структуру проекта"
```

### CLI — REST API сервер
```bash
python cli.py --server
# API: http://127.0.0.1:8000
```

### CLI — Telegram-бот
```bash
python cli.py --telegram
```

### Docker
```bash
docker build -t velocity-claw .
docker run --env-file .env -p 8000:8000 velocity-claw
```

## API

```bash
# Здоровье
curl http://127.0.0.1:8000/health

# Запустить задачу
curl -X POST http://127.0.0.1:8000/task \
  -H "Content-Type: application/json" \
  -d '{"task": "Проанализируй текущую структуру проекта"}'

# Статус агента
curl http://127.0.0.1:8000/status
```

## Тесты

```bash
python -m pytest tests/ -q
# или
python -m unittest discover tests
```

Все 18 тестов проходят: agent, planner, router, tools, memory.

## Структура проекта

```
velocity_claw/
  config/      — Settings, load_settings
  core/        — VelocityClawAgent, runner
  planner/     — Planner, prompts
  executor/    — Executor
  models/      — ModelRouter, providers
  tools/       — fs, shell, git, http, docker, editor
  memory/      — MemoryStore (SQLite)
  security/    — SecurityManager, AccessProfile
  logs/        — get_logger
  prompts/     — system, safe_mode
  api/         — FastAPI server
  telegram_bot/— Telegram bot
```
