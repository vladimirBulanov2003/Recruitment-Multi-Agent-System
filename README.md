# Recruitment Agent Prototype

Многоагентный прототип для найма, который соединяет LLM-оркестратора, диспетчер задач и набор мок-сервисов (ATS, AI Matching, Calling Agent). Архитектура, бизнес-логика и интеграции написаны мной; визуальный интерфейс Streamlit (`streamlit/streamlit.py`) был сгенерирован LLM специально для ускорения разработки.

## Что решает система
- Общается с рекрутером, формирует пайплайны найма и исполняет их по шагам.
- Затем каждую задачу из конкретного пайплайна выполняет в Task Manager и рассылает события через WebSocket к агенту.
- Показывает ход выполнения и найденных кандидатов в Streamlit-дэшборде, который обновляется в реальном времени.
- Система способна генерировать и выполнять сразу несколько задач, например, можно искать питон разработчиков из США и java из России одновременно (пример показан в видео)

## Архитектура
- **Chat Bot Agent (`chat_bot_agent/`)** — главный LLM-оркестратор (Google ADK + LiteLLM). Генерирует пайплайны, вызывает инструменты для ATS/AI Matching/Voice Bot, синхронизирует state.
- **Pipeline Generator (`chat_bot_agent/sub_agents/...`)** — подчинённый агент, генерирующий структуры пайплайнов.
- **Main Agent API (`server_agent/server_for_agent.py`)** — FastAPI сервер над Runner из ADK: создаёт/удаляет сессии, принимает сообщения от UI, ретранслирует события в WebSocket `ws://127.0.0.1:9999/ws/update_session_state`.
- **Task Manager (`task_manager/`)** — оркестратор задач. Поднимает async клиентов для ATS/AI Matching/Voice Bot, триггерит их, добавляет обновления в агента и Streamlit (`http://localhost:8765`).
- **Mock services (`services/*`)**
  - `atsservice/ats_server`: возвращает случайные резюме из `new_can.json`.
  - `ai_matching_service/ai_matching_server`: батчит кандидатов и обращается к ADK-агенту `services/agent`.
  - `calling_agent`: симулирует звонки и отдаёт события по кандидатам.
- **ADK Agent (`services/agent/resume_search_llm/`)** — отдельный `adk api_server` с LiteLLM моделью для поиска кандидатов по JSON-input.
- **Streamlit WebSocket server (`streamlit/server.py`)** — посредник между Task Manager и UI, пушит статус пайплайнов и найденных кандидатов.
- **Streamlit Dashboard (`streamlit/streamlit.py`)** — чат + таблицы пайплайнов, автообновление через `/tmp/maya_pipelines.json` и сообщения WebSocket. Повторюсь: этот UI сгенерирован LLM.

##  Пример работы
1. Пользователь общается с Chat Bot Agent → генерируется пайплайн (ATS → AI Matching → Voice Bot).
2. Agent подтверждает план, вызывает Task Manager через инструмент.
3. Task Manager дергает соответствующие mock-сервисы; результаты пишутся в хранилище состояния агента и рассылаются Streamlit через HTTP/WebSocket.
4. Streamlit читает `/tmp/maya_pipelines.json` + уведомления, подсвечивает статусы, показывает найденных кандидатов и звонки.

### Требования
- Python 3.12+.
- Доступ к OpenAI API (LiteLLM). Можно, в целом, использовать gemini.


### Ручной запуск по сервисам
Все команды выполняются из корневой папки, в которой находится проект:
```bash

uvicorn services.atsservice.ats_server.server:app --host 0.0.0.0 --port 8080

uvicorn services.ai_matching_service.ai_matching_server.server:app --host 127.0.0.1 --port 8001

python3 services/calling_agent/server.py

cd task_manager && python3 server.py

python3 -m server_agent.server_for_agent

adk api_server services/agent

python3 streamlit/server.py

streamlit run streamlit/streamlit.py --server.port 8501
```
Интерфейс Streamlit был сгенерирован LLM для ускорения прототипа; остальная архитектура и логика написаны вручную.

## Структура
- `chat_bot_agent/` — корневой агент + инструменты.
- `services/agent/` — ADK агент для AI Matching.
- `services/atsservice/`, `services/ai_matching_service/`, `services/calling_agent/` — мок-бэкенды.
- `task_manager/` — планировщик и маршрутизатор заданий.
- `streamlit/` — WebSocket сервер и UI (сгенерирован LLM).
- `launch_mocks/` — сценарии запуска и вспомогательные утилиты.

## Баги
- В проекте есть баги, которые связаны с отсутствием валидации во время вызова инструмента. Так же бывают неточности во время работы прототипа AI Matching.

