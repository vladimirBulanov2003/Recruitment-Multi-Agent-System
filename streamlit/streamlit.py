
import streamlit as st
import asyncio
import websockets
import json
from threading import Thread
import random
from pathlib import Path
import time

st.set_page_config(layout="wide", page_title="Chat + Tasks Dashboard")

# === ПУТЬ К ВРЕМЕННОМУ ФАЙЛУ ===
PIPELINES_FILE = Path("/tmp/maya_pipelines.json")

# === ОЧИСТКА СТАРЫХ ДАННЫХ ПРИ СТАРТЕ (ОДИН РАЗ) ===
@st.cache_resource
def initialize_app_once():
    """Инициализация приложения - выполняется ОДИН раз"""
    # Удаляем старый файл при первом запуске
    if PIPELINES_FILE.exists():
        PIPELINES_FILE.unlink()
        print("🗑️ Старые pipeline удалены при запуске приложения")
    
    # Удаляем файл с уведомлениями о кандидатах
    candidates_file = Path("/tmp/maya_candidates_notifications.json")
    if candidates_file.exists():
        candidates_file.unlink()
        print("🗑️ Старые уведомления о кандидатах удалены")
    
    # Создаем сессию агента
    try:
        import httpx
        response = httpx.post("http://0.0.0.0:9999/users/0/sessions/0/create_session", timeout=5.0)
        if response.status_code == 200:
            print("✅ Agent session created ONCE (user_id=0, session_id=0)")
            return True
    except Exception as e:
        print(f"⚠️ Failed to create agent session: {e}")
        return False

# Вызываем инициализацию один раз
_ = initialize_app_once()

# === ЦВЕТА ДЛЯ СТАТУСОВ ===
status_colors = {
    "COMPLETED": "#22c55e",
    "FAILED": "#ef4444",
    "RUNNING": "#f59e0b",
    "NOT_STARTED": "#6b7280",
    "INTERRUPTED": "#ef4444"  # Красный для прерванных задач
}

# === ИНИЦИАЛИЗАЦИЯ STATE ===
if "tasks" not in st.session_state:
    st.session_state.tasks = []

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"user": "System", "text": "Добро пожаловать в чат!"}
    ]

if "ws_connected" not in st.session_state:
    st.session_state.ws_connected = False

if "loaded_pipeline_ids" not in st.session_state:
    st.session_state.loaded_pipeline_ids = set()

if "last_file_mtime" not in st.session_state:
    st.session_state.last_file_mtime = 0

if "processed_candidates" not in st.session_state:
    st.session_state.processed_candidates = set()

if "waiting_for_agent" not in st.session_state:
    st.session_state.waiting_for_agent = False

if "pending_message" not in st.session_state:
    st.session_state.pending_message = None

async def websocket_listener():
    """Слушает WebSocket и обрабатывает два типа сообщений:
    1. Новый pipeline (при создании)
    2. Обновление статуса компонента (при выполнении задач)
    """
    uri = "ws://localhost:8765/ws/pipelines"
    
    while True:
        try:
            async with websockets.connect(uri, ping_interval=20) as websocket:
                print("✅ Connected to WebSocket server")
                
                while True:
                    # Получаем данные от сервера
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    # === ТИП 1: Обновление статуса компонента ===
                    if data.get("type") == "status_update":
                        print(f"📝 Status update for pipeline #{data['index_of_pipeline']}, component #{data['index_of_component']}")
                        
                        # Специальное логирование для INTERRUPTED
                        if data.get("state_changes", {}).get("INTERRUPTED"):
                            print(f"🛑 INTERRUPTED: Pipeline #{data['index_of_pipeline']}, Component #{data['index_of_component']}")
                        
                        try:
                            # Обновляем файл
                            if PIPELINES_FILE.exists():
                                # Читаем с проверкой на пустой файл
                                with open(PIPELINES_FILE, "r") as f:
                                    content = f.read().strip()
                                    if not content:
                                        pipelines = []
                                    else:
                                        pipelines = json.loads(content)
                                
                                # Находим нужный pipeline и обновляем статус
                                for pipeline in pipelines:
                                    if pipeline["id"] == data["index_of_pipeline"]:
                                        component = pipeline["components"][data["index_of_component"]]
                                        
                                        # Обновляем статусы
                                        for key, value in data["state_changes"].items():
                                            component["status"][key] = value
                                        
                                        # Если есть дополнительные данные (например, для voice_bot)
                                        if "clients_stats" in data:
                                            component["clients_stats"] = data["clients_stats"]
                                        
                                        # Сохраняем обратно
                                        with open(PIPELINES_FILE, "w") as f:
                                            json.dump(pipelines, f, indent=2)
                                        
                                        print(f"✅ Updated status in file: {data['state_changes']}")
                                        break
                        
                        except json.JSONDecodeError as e:
                            print(f"❌ JSON decode error: {e}")
                        except Exception as e:
                            print(f"❌ Error updating status: {e}")
                    
                    # === ТИП 2: Новый pipeline ===
                    elif "pipeline" in data and "index" in data:
                        print(f"📥 Received new pipeline #{data['index']}")
                        
                        try:
                            # Читаем существующие pipeline
                            if PIPELINES_FILE.exists():
                                with open(PIPELINES_FILE, "r") as f:
                                    content = f.read().strip()
                                    if not content:
                                        pipelines = []
                                    else:
                                        pipelines = json.loads(content)
                            else:
                                pipelines = []
                            
                            # Добавляем новый
                            new_pipeline = {
                                "id": data["index"],
                                "name": f"Pipeline #{data['index']}",
                                "components": data["pipeline"]["chain"],
                                "timestamp": time.time()
                            }
                            
                            # Проверяем, не добавлен ли уже
                            existing_ids = [p["id"] for p in pipelines]
                            if data["index"] not in existing_ids:
                                pipelines.append(new_pipeline)
                                
                                # Сохраняем обратно
                                with open(PIPELINES_FILE, "w") as f:
                                    json.dump(pipelines, f, indent=2)
                                
                                print(f"💾 Saved new pipeline #{data['index']} to file")
                            else:
                                print(f"⚠️ Pipeline #{data['index']} already exists, skipping")
                        
                        except json.JSONDecodeError as e:
                            print(f"❌ JSON decode error: {e}")
                        except Exception as e:
                            print(f"❌ Error saving pipeline: {e}")
                    
                    # === ТИП 3: Найденные кандидаты ===
                    elif data.get("type") == "candidates_found":
                        print(f"📋 WebSocket received {data['count']} candidates for pipeline #{data['index_of_pipeline']}")
                        print(f"📋 Candidates data: {data['candidates'][:1] if data['candidates'] else 'empty'}")  # Первый кандидат для проверки
                        
                        try:
                            candidates_file = Path("/tmp/maya_candidates_notifications.json")
                            
                            if candidates_file.exists():
                                with open(candidates_file, "r") as f:
                                    content = f.read().strip()
                                    notifications = json.loads(content) if content else []
                            else:
                                notifications = []
                            
                            # Добавляем новое уведомление
                            notifications.append({
                                "pipeline_id": data["index_of_pipeline"],
                                "candidates": data["candidates"],
                                "count": data["count"],
                                "timestamp": time.time()
                            })
                            
                            # Сохраняем
                            with open(candidates_file, "w") as f:
                                json.dump(notifications, f, indent=2)
                            
                            print(f"✅ Saved candidates notification to file. Total notifications in file: {len(notifications)}")
                        
                        except Exception as e:
                            print(f"❌ Error saving candidates: {e}")
                    
                    else:
                        print(f"⚠️ Unknown message type: {data}")
                    
                    # Отправляем ping обратно (keep-alive)
                    try:
                        await websocket.send("ping")
                    except:
                        pass
                    
        except Exception as e:
            print(f"❌ WebSocket error: {e}")
            await asyncio.sleep(2)  # Переподключение через 2 сек

def start_websocket_thread():
    """Запускает WebSocket listener в отдельном потоке"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(websocket_listener())

# Запускаем WebSocket listener один раз (singleton через cache_resource)
@st.cache_resource
def get_websocket_thread():
    """Создает singleton WebSocket поток"""
    ws_thread = Thread(target=start_websocket_thread, daemon=True)
    ws_thread.start()
    print("🚀 WebSocket thread started (singleton)")
    return ws_thread

# Инициализируем поток
_ = get_websocket_thread()

# === ЗАГРУЗКА И СИНХРОНИЗАЦИЯ PIPELINE ИЗ ФАЙЛА ===
def load_and_sync_pipelines():
    """Читает pipeline из файла и синхронизирует с session_state"""
    if PIPELINES_FILE.exists():
        try:
            # Проверяем, изменился ли файл
            current_mtime = PIPELINES_FILE.stat().st_mtime
            
            with open(PIPELINES_FILE, "r") as f:
                content = f.read().strip()
                if not content:
                    return
                pipelines = json.loads(content)
            
            # Создаем словарь для быстрого поиска
            file_pipelines = {p["id"]: p for p in pipelines}
            
            # Обновляем существующие и добавляем новые
            existing_ids = set()
            for i, task in enumerate(st.session_state.tasks):
                task_id = task["id"]
                existing_ids.add(task_id)
                
                # Если pipeline есть в файле, обновляем его
                if task_id in file_pipelines:
                    st.session_state.tasks[i] = file_pipelines[task_id]
            
            # Добавляем новые pipeline
            for pipeline_id, pipeline in file_pipelines.items():
                if pipeline_id not in existing_ids:
                    st.session_state.tasks.append(pipeline)
                    st.session_state.loaded_pipeline_ids.add(pipeline_id)
                    st.session_state.messages.append({
                        "user": "System",
                        "text": f"🆕 Новый pipeline #{pipeline_id} создан!"
                    })
            
            st.session_state.ws_connected = True
            st.session_state.last_file_mtime = current_mtime
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error: {e}")
        except Exception as e:
            print(f"❌ Error loading pipelines: {e}")

# === ЗАГРУЗКА УВЕДОМЛЕНИЙ О КАНДИДАТАХ ===
def load_candidates_notifications():
    """Загружает уведомления о кандидатах и добавляет в чат"""
    candidates_file = Path("/tmp/maya_candidates_notifications.json")
    
    print(f"🔍 Checking candidates file: exists={candidates_file.exists()}")
    
    if candidates_file.exists():
        try:
            with open(candidates_file, "r") as f:
                content = f.read().strip()
                if not content:
                    print("⚠️ Candidates file is empty")
                    return
                notifications = json.loads(content)
            
            print(f"📋 Found {len(notifications)} candidate notifications")
            
            # Обрабатываем только новые уведомления
            for notif in notifications:
                notif_id = f"{notif['pipeline_id']}_{notif['timestamp']}"
                
                if notif_id not in st.session_state.processed_candidates:
                    # Формируем красивое сообщение
                    if notif["count"] == 0:
                        message_text = "❌ **Кандидаты не найдены**\n\nПо указанным критериям для Pipeline #{} не удалось найти подходящих кандидатов.".format(notif['pipeline_id'])
                    else:
                        # Простое и читаемое отображение кандидатов
                        header = f"<div style='font-size: 16px; font-weight: bold; color: #4CAF50; margin-bottom: 15px; border-bottom: 2px solid #4CAF50; padding-bottom: 8px;'>✅ Найдено {notif['count']} кандидатов для Pipeline #{notif['pipeline_id']}</div>"
                        
                        candidates_html = []
                        for i, candidate in enumerate(notif["candidates"], 1):
                            name = candidate.get("person_name", "Unknown")
                            headline = candidate.get("headline", "")
                            location = candidate.get("location", "")
                            email = candidate.get("contact_email", "")
                            phone = candidate.get("telephone_number", "")
                            skills = candidate.get("skills", [])
                            
                            # Простая карточка кандидата (прозрачный фон, белый текст)
                            candidate_card = f"<div style='border-left: 3px solid #2196F3; padding: 12px; margin: 12px 0; background-color: transparent;'><div style='font-size: 16px; font-weight: bold; color: white; margin-bottom: 6px;'>{i}. {name}</div>"
                            
                            if headline:
                                candidate_card += f"<div style='margin: 4px 0; color: white;'>📋 {headline}</div>"
                            if location:
                                candidate_card += f"<div style='margin: 4px 0; color: white;'>📍 {location}</div>"
                            if email:
                                candidate_card += f"<div style='margin: 4px 0; color: white;'>✉️ {email}</div>"
                            if phone:
                                candidate_card += f"<div style='margin: 4px 0; color: white;'>📞 {phone}</div>"
                            if skills:
                                skills_str = ", ".join(skills[:5])
                                if len(skills) > 5:
                                    skills_str += f" <span style='background: #555; color: white; padding: 2px 6px; border-radius: 4px; font-size: 12px;'>+{len(skills)-5} еще</span>"
                                candidate_card += f"<div style='margin: 6px 0; color: white;'>🔧 <strong>Skills:</strong> {skills_str}</div>"
                            
                            candidate_card += "</div>"
                            candidates_html.append(candidate_card)
                        
                        message_text = header + "".join(candidates_html)
                    
                    st.session_state.messages.append({
                        "user": "System",
                        "text": message_text,
                        "type": "candidates"
                    })
                    
                    st.session_state.processed_candidates.add(notif_id)
                    print(f"✅ Added candidates to chat. Total messages: {len(st.session_state.messages)}")
                    print(f"🔍 HTML length: {len(message_text)} chars")
                    print(f"🔍 First 200 chars: {message_text[:200]}")
                    
                    # Флаг для принудительного обновления
                    st.session_state.candidates_updated = True
        
        except Exception as e:
            print(f"❌ Error loading candidates: {e}")

# Загружаем и синхронизируем pipeline при каждом обновлении
load_and_sync_pipelines()

# Загружаем уведомления о кандидатах
load_candidates_notifications()

# === LAYOUT ===
col_chat, col_dash = st.columns([3, 1.5])

# --- CHAT (с auto-refresh для кандидатов) ---
@st.fragment(run_every=2)  # Обновляется каждые 2 секунды
def chat_display_fragment():
    """Отображение чата с автообновлением для кандидатов"""
    # ВАЖНО: Загружаем кандидатов ПЕРЕД отображением
    # Это должно работать т.к. fragment может читать и изменять session_state
    load_candidates_notifications()
    
    # Индикатор подключения
    if st.session_state.ws_connected:
        st.success("🟢 WebSocket подключен")
    else:
        st.warning("🟡 Подключение к WebSocket...")
    
    # Отладка: показываем количество сообщений
    st.caption(f"📝 Всего сообщений: {len(st.session_state.messages)}")
    
    # Контейнер для чата
    chat_container = st.container(height=600, border=True)
    with chat_container:
        for idx, msg in enumerate(st.session_state.messages):
            user = msg['user']
            text = msg['text']
            msg_type = msg.get('type', 'normal')
            
            # Разные стили для разных типов сообщений
            if msg_type == "candidates":
                # Кандидаты - отображаем HTML напрямую
                print(f"🎨 Rendering candidates HTML (length={len(text)})")
                st.markdown(text, unsafe_allow_html=True)
            elif user == "System":
                # System - по центру, мелким текстом
                st.markdown(f"""
                <div style='text-align: center; color: #666; font-size: 13px; margin: 8px 0;'>
                ℹ️ {text}
                </div>
                """, unsafe_allow_html=True)
            elif user == "Maya AI":
                # Maya AI - слева, как в мессенджере
                st.markdown(f"""
                <div style='display: flex; justify-content: flex-start; margin: 10px 0;'>
                    <div style='max-width: 70%; background-color: #0084ff; color: white; padding: 12px 16px; 
                                border-radius: 18px; border-bottom-left-radius: 4px;'>
                        <div style='font-weight: 500; margin-bottom: 4px;'>🤖 Maya AI</div>
                        <div style='line-height: 1.5;'>{text}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                # Пользователь - справа, как в мессенджере
                st.markdown(f"""
                <div style='display: flex; justify-content: flex-end; margin: 10px 0;'>
                    <div style='max-width: 70%; background-color: #0084ff; color: white; padding: 12px 16px; 
                                border-radius: 18px; border-bottom-right-radius: 4px;'>
                        <div style='line-height: 1.5;'>{text}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        # JavaScript для автоскролла вниз
        st.markdown("""
        <script>
        var chatContainer = window.parent.document.querySelector('[data-testid="stVerticalBlock"]');
        if (chatContainer) {
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
        </script>
        """, unsafe_allow_html=True)

with col_chat:
    st.header("💬 Chat")
    
    # Отображаем чат через fragment
    chat_display_fragment()

# === ОБРАБОТКА ОЖИДАЮЩЕГО ЗАПРОСА К АГЕНТУ ===
# Это выполняется ДО формы, чтобы показать спиннер и получить ответ
if st.session_state.waiting_for_agent and st.session_state.pending_message:
    with col_chat:
        with st.spinner("Maya AI думает..."):
            try:
                import httpx
                user_message = st.session_state.pending_message
                print(f"📤 Sending message to agent: {user_message}")
                response = httpx.post(
                    "http://127.0.0.1:9999/run",
                    params={"user_id": "0", "session_id": "0", "message": user_message},
                    timeout=None
                )
                print(f"📥 Response status: {response.status_code}")
                
                if response.status_code == 200:
                    response_data = response.json()
                    print(f"📥 Response data: {response_data}")
                    answer = response_data.get("answer", "Нет ответа")
                    print(f"📥 Agent answer: {answer}")
                    
                    if answer and answer != "Нет ответа":
                        st.session_state.messages.append({"user": "Maya AI", "text": answer})
                        print(f"✅ Message added to session_state. Total messages: {len(st.session_state.messages)}")
                    else:
                        st.session_state.messages.append({
                            "user": "System", 
                            "text": "⚠️ Агент не вернул ответ"
                        })
                        print(f"⚠️ No answer message added. Total messages: {len(st.session_state.messages)}")
                else:
                    st.session_state.messages.append({
                        "user": "System", 
                        "text": f"❌ Ошибка сервера: {response.status_code}"
                    })
            except httpx.TimeoutException:
                print("⏱️ Timeout exception")
                st.session_state.messages.append({
                    "user": "System", 
                    "text": "⏱️ Превышено время ожидания ответа"
                })
            except Exception as e:
                print(f"❌ Exception: {type(e).__name__}: {str(e)}")
                st.session_state.messages.append({
                    "user": "System", 
                    "text": f"❌ Ошибка соединения: {str(e)}"
                })
            
            # Сбрасываем флаги
            st.session_state.waiting_for_agent = False
            st.session_state.pending_message = None
            st.rerun()

# --- DASHBOARD (с auto-refresh через fragment) ---
@st.fragment(run_every=2)  # Обновляется каждые 2 секунды
def dashboard_fragment():
    """Dashboard с автоматическим обновлением без перезагрузки всей страницы"""
    # Перезагружаем данные при каждом обновлении fragment
    load_and_sync_pipelines()
    load_candidates_notifications()
    
    st.header("📊 Tasks Dashboard")
    
    if not st.session_state.tasks:
        st.info("🔄 Ожидание pipeline от агента...")
    
    for task in st.session_state.tasks:
        with st.expander(f"🧱 {task['name']}", expanded=True):
            comps = task["components"]

            # === Flow layout ===
            flow_html = ""
            for i, comp in enumerate(comps):
                step_name = comp["component_type"].replace("_", " ").title()
                
                # Определяем цвет: INTERRUPTED = красный, иначе стандартная логика
                if comp["status"].get("INTERRUPTED"):
                    color = "#ef4444"  # Красный для прерванных
                elif comp["status"].get("COMPLETED"):
                    color = "#22c55e"  # Зеленый для завершенных
                elif comp["status"].get("RUNNING"):
                    color = "#f59e0b"  # Оранжевый для выполняющихся
                else:
                    color = "#6b7280"  # Серый для не начатых
                
                flow_html += f"""
                    <div style='display:inline-block; text-align:center; margin:2px;'>
                        <div style='background:{color}15; border:1px solid {color};
                                    border-radius:6px; padding:4px 10px; min-width:110px;
                                    font-size:13px;'>
                            <b style='color:{color};'>{i+1}. {step_name}</b>
                        </div>
                    </div>
                """
                if i < len(comps) - 1:
                    flow_html += "<span style='font-size:18px; color:#9ca3af;'> ➜ </span>"

            st.markdown(flow_html, unsafe_allow_html=True)
            st.divider()

            # === Мини-карточки компонентов ===
            for idx, comp in enumerate(comps):
                # Проверяем, прервана ли Voice Bot задача
                is_voice_bot = comp["component_type"] == "voice_bot_component"
                is_interrupted = comp["status"].get("INTERRUPTED", False)
                
                with st.container(border=True):
                    # Заголовок компонента (красный для прерванного Voice Bot)
                    if is_voice_bot and is_interrupted:
                        st.markdown(
                            f"<h4 style='color: #ef4444; margin: 0;'>🎤 {idx+1}. Voice Bot Component</h4>",
                            unsafe_allow_html=True
                        )
                        st.error("🛑 **ЗАДАЧА ПРЕРВАНА ПОЛЬЗОВАТЕЛЕМ**")
                    else:
                        st.markdown(
                            f"**{idx+1}. {comp['component_type'].replace('_', ' ').title()}**",
                            help="Информация о компоненте"
                        )

                    cols = st.columns(2)
                    with cols[0]:
                        status_html = ""
                        for key, val in comp["status"].items():
                            color = status_colors.get(key, "#999")
                            dot = f"<span style='color:{color}; font-size:14px;'>●</span>"
                            if val:
                                # Красный текст для прерванного Voice Bot
                                if is_voice_bot and is_interrupted:
                                    status_html += f"{dot} <b style='color: #ef4444;'>{key}</b><br>"
                                else:
                                    status_html += f"{dot} <b>{key}</b><br>"
                        st.markdown(status_html, unsafe_allow_html=True)

                    with cols[1]:
                        for k, v in comp.items():
                            if k in ["status", "clients_stats", "component_type"]:
                                continue
                            # Красный текст для прерванного Voice Bot
                            if is_voice_bot and is_interrupted:
                                st.markdown(f"<span style='font-size:13px; color: #ef4444;'><b>{k}:</b> {v}</span>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<span style='font-size:13px;'><b>{k}:</b> {v}</span>", unsafe_allow_html=True)

                    # Voice bot dashboard mini
                    if comp["component_type"] == "voice_bot_component" and "clients_stats" in comp:
                        stats = comp["clients_stats"]
                        total = stats.get("total", 0)
                        answered = stats.get("answered", 0)
                        accepted = stats.get("accepted_offer", 0)
                        declined = stats.get("declined_offer", 0)

                        if total > 0:
                            # Красный заголовок для прерванной задачи
                            if is_interrupted:
                                st.markdown("📞 <b style='color: #ef4444;'>Voice Bot Statistics (INTERRUPTED):</b>", unsafe_allow_html=True)
                            else:
                                st.markdown("📞 <b>Voice Bot Statistics:</b>", unsafe_allow_html=True)
                            
                            # Общая статистика
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Всего", total)
                            with col2:
                                st.metric("Ответили", answered)
                            with col3:
                                answer_rate = (answered / total * 100) if total > 0 else 0
                                st.metric("% ответов", f"{answer_rate:.0f}%")
                            
                            # Прогресс-бары
                            if answered > 0:
                                st.markdown("**Результаты звонков:**")
                                
                                accept_rate = accepted / answered if answered > 0 else 0
                                st.progress(accept_rate)
                                st.caption(f"✅ Согласились: {accepted} из {answered} ({accept_rate*100:.0f}%)")
                                
                                # НОВОЕ: Показываем список кандидатов, которые ПРИНЯЛИ предложение
                                accepted_candidates = stats.get("accepted_candidates", [])
                                if accepted_candidates:
                                    with st.expander(f"👥 Кто принял предложение ({len(accepted_candidates)})"):
                                        for candidate in accepted_candidates:
                                            st.markdown(f"- **{candidate['name']}**")
                                
                                decline_rate = declined / answered if answered > 0 else 0
                                st.progress(decline_rate)
                                st.caption(f"❌ Отказались: {declined} из {answered} ({decline_rate*100:.0f}%)")
                                
                                # НОВОЕ: Показываем список кандидатов, которые ОТКЛОНИЛИ предложение
                                declined_candidates = stats.get("declined_candidates", [])
                                if declined_candidates:
                                    with st.expander(f"👥 Кто отклонил предложение ({len(declined_candidates)})"):
                                        for candidate in declined_candidates:
                                            st.markdown(f"- **{candidate['name']}**")

    st.caption(f"🛰 Всего pipeline: {len(st.session_state.tasks)}")

# Вызываем dashboard fragment
with col_dash:
    dashboard_fragment()

# === ВВОД СООБЩЕНИЙ (chat_input с Enter) - В САМОМ КОНЦЕ ===
# Размещаем ПОСЛЕ всех колонок и фрагментов, чтобы не пропадал
user_input = st.chat_input("Введите сообщение...")

if user_input:
    # Добавляем сообщение пользователя СРАЗУ
    st.session_state.messages.append({"user": "Вы", "text": user_input})
    
    # Устанавливаем флаг для отправки на агента
    st.session_state.waiting_for_agent = True
    st.session_state.pending_message = user_input
    
    # Перезагружаем страницу - сообщение пользователя отобразится сразу
    st.rerun()