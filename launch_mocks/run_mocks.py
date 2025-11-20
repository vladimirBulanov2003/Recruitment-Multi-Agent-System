#!/usr/bin/env python3
"""
Скрипт для автоматического запуска всех mock-сервисов из папки services.
"""
import subprocess
import signal
import sys
import os
from pathlib import Path
import time
import socket

# Конфигурация сервисов: папка -> порт
# Можно добавить или изменить порты по необходимости
SERVICE_PORTS = {
    "atsservice/ats_server": 8080,  # Изменил с 80 на 8080 (не требует root)
    "ai_matching_service/ai_matching_server": 8001,
    "calling_agent": 8002,
}

# Дополнительные сервисы (не mock-сервисы)
ADDITIONAL_SERVICES = {
    "streamlit_server": {
        "path": "streamlit/server.py",
        "port": 8003,
        "working_dir": "streamlit",
        "command": ["python3", "server.py"]
    },
    "main_agent": {
        "path": "server_agent/server_for_agent.py", 
        "port": 8004,
        "working_dir": ".",
        "command": ["python3", "-m", "server_agent.server_for_agent"]
    },
    "streamlit_ui": {
        "path": "streamlit/streamlit.py",
        "port": 8501,  # Стандартный порт streamlit
        "working_dir": "streamlit", 
        "command": ["streamlit", "run", "streamlit.py"]
    }
}

# Список запущенных процессов
PROCESSES = []

# ADK агент (опционально, запускается как отдельный процесс)
ADK_AGENT_PATH = "services/agent"
ADK_AGENT_PORT = 8000

def is_port_in_use(port):
    """Проверяет, занят ли порт."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return False
        except OSError:
            return True

def kill_process_on_port(port):
    """Убивает процесс на указанном порту (macOS/Linux)."""
    try:
        # Находим PID процесса на порту
        result = subprocess.run(
            ['lsof', '-ti', f':{port}'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                try:
                    pid_int = int(pid)
                    os.kill(pid_int, signal.SIGTERM)
                    print(f"   ⚠️  Убил процесс {pid_int} на порту {port}")
                    time.sleep(0.5)
                    # Проверяем, не остался ли процесс
                    try:
                        os.kill(pid_int, 0)  # Проверка существования
                        # Если всё ещё существует, убиваем жёстче
                        os.kill(pid_int, signal.SIGKILL)
                        print(f"   ⚠️  Принудительно убил процесс {pid_int}")
                    except ProcessLookupError:
                        pass  # Процесс уже не существует
                except (ValueError, ProcessLookupError, PermissionError):
                    pass
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return False
    return False

def check_and_free_ports(services_config, additional_services=None):
    """Проверяет порты и предлагает освободить их."""
    ports_in_use = []
    # Проверяем все сервисы
    for name, config in services_config.items():
        port = config["port"]
        if is_port_in_use(port):
            ports_in_use.append((name, port))
    
    # Проверяем дополнительные сервисы
    if additional_services:
        for name, config in additional_services.items():
            port = config["port"]
            if is_port_in_use(port):
                ports_in_use.append((name, port))
    
    if not ports_in_use:
        return True
    
    print("\n⚠️  Обнаружены занятые порты:")
    for name, port in ports_in_use:
        print(f"   • {name}: порт {port}")
    
    print("\n🔧 Пытаюсь освободить порты...")
    all_freed = True
    for name, port in ports_in_use:
        if kill_process_on_port(port):
            # Даём время процессу завершиться
            time.sleep(1)
            if is_port_in_use(port):
                print(f"   ❌ Не удалось освободить порт {port} для {name}")
                all_freed = False
            else:
                print(f"   ✅ Порт {port} освобождён")
        else:
            print(f"   ❌ Не удалось найти процесс на порту {port}")
            all_freed = False
    
    if not all_freed:
        print("\n❌ Некоторые порты всё ещё заняты!")
        print("   Попробуйте вручную убить процессы:")
        for _, port in ports_in_use:
            print(f"   lsof -ti:{port} | xargs kill -9")
        return False
    
    print("✅ Все порты освобождены!\n")
    return True

def find_server_files():
    """Находит все server.py файлы в папке services."""
    services_dir = Path(__file__).parent / "services"
    server_files = {}
    
    for root, dirs, files in os.walk(services_dir):
        if "server.py" in files:
            rel_path = os.path.relpath(root, services_dir)
            server_path = os.path.join(root, "server.py")
            
            # Определяем порт из конфига или используем автоматический
            port = SERVICE_PORTS.get(rel_path)
            if port is None:
                # Если порт не указан, пропускаем или используем дефолтный
                print(f"⚠️  Порт не указан для {rel_path}, пропускаем...")
                continue
            
            server_files[rel_path] = {
                "path": server_path,
                "port": port,
                "working_dir": root
            }
    
    return server_files

def start_service(name, config):
    """Запускает один сервис."""
    server_path = config["path"]
    port = config["port"]
    working_dir = config["working_dir"]
    
    # Получаем абсолютный путь к корневой директории проекта
    project_root = Path(__file__).parent.absolute()
    services_dir = project_root / "services"
    
    # Устанавливаем PYTHONPATH: корень проекта и services
    env = os.environ.copy()
    python_path = f"{project_root}:{services_dir}"
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{python_path}:{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = python_path
    
    # Используем простой server:app с правильной рабочей директорией
    # working_dir уже указывает на папку сервиса (например, services/atsservice/ats_server)
    cmd = [
        sys.executable, "-m", "uvicorn",
        "server:app",
        "--host", "127.0.0.1",
        "--port", str(port)
    ]
    
    print(f"🚀 Запускаю {name} на порту {port}...")
    print(f"   Команда: {' '.join(cmd)}")
    print(f"   Рабочая директория: {working_dir}")
    
    process = subprocess.Popen(
        cmd,
        cwd=working_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    PROCESSES.append({
        "name": name,
        "process": process,
        "port": port
    })
    
    return process

def start_additional_service(name, config):
    """Запускает дополнительный сервис (не mock)."""
    port = config["port"]
    working_dir = config["working_dir"]
    command = config["command"]
    
    # Получаем абсолютный путь к корневой директории проекта
    project_root = Path(__file__).parent.absolute()
    
    # Устанавливаем PYTHONPATH
    env = os.environ.copy()
    python_path = f"{project_root}:{project_root / 'services'}"
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{python_path}:{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = python_path
    
    # Определяем рабочую директорию
    if working_dir == ".":
        cwd = project_root
    else:
        cwd = project_root / working_dir
    
    print(f"🚀 Запускаю {name} на порту {port}...")
    print(f"   Команда: {' '.join(command)}")
    print(f"   Рабочая директория: {cwd}")
    
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    PROCESSES.append({
        "name": name,
        "process": process,
        "port": port
    })
    
    return process

def start_adk_agent():
    """Запускает ADK-агента как `adk api_server services/agent_for_ai_matching`."""
    project_root = Path(__file__).parent.absolute()
    env = os.environ.copy()

    # Команда, как вы запускаете вручную
    cmd = [
        "adk", "api_server", ADK_AGENT_PATH
    ]

    print(f"🚀 Запускаю ADK агента ({ADK_AGENT_PATH}) на порту {ADK_AGENT_PORT}...")
    print(f"   Команда: {' '.join(cmd)}")
    print(f"   Рабочая директория: {project_root}")

    try:
        process = subprocess.Popen(
            cmd,
            cwd=project_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
    except FileNotFoundError:
        # Fallback: пробуем через активный интерпретатор
        fallback_cmd = [sys.executable, "-m", "adk", "api_server", ADK_AGENT_PATH]
        print("⚠️  Команда 'adk' не найдена в PATH. Пробую запуск через python -m adk:")
        print(f"   Команда: {' '.join(fallback_cmd)}")
        process = subprocess.Popen(
            fallback_cmd,
            cwd=project_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

    PROCESSES.append({
        "name": f"ADK Agent ({ADK_AGENT_PATH})",
        "process": process,
        "port": ADK_AGENT_PORT
    })

    return process

def signal_handler(sig, frame):
    """Обработчик сигнала для корректного завершения всех процессов."""
    print("\n\n🛑 Останавливаю все сервисы...")
    for proc_info in PROCESSES:
        try:
            proc_info["process"].terminate()
        except:
            pass
    
    # Даём время на завершение
    time.sleep(2)
    
    # Если процессы ещё живы, убиваем принудительно
    for proc_info in PROCESSES:
        try:
            if proc_info["process"].poll() is None:
                proc_info["process"].kill()
        except:
            pass
    
    print("✅ Все сервисы остановлены")
    sys.exit(0)

def main():
    """Основная функция."""
    print("=" * 60)
    print("🔍 Поиск mock-сервисов в папке services...")
    print("=" * 60)
    
    services = find_server_files()
    
    if not services:
        print("❌ Сервисы не найдены!")
        return
    
    print(f"\n📋 Найдено mock-сервисов: {len(services)}")
    print(f"📋 Дополнительных сервисов: {len(ADDITIONAL_SERVICES)}")
    print(f"📋 ADK агент: 1\n")
    
    # Проверяем и освобождаем порты
    if not check_and_free_ports(services, ADDITIONAL_SERVICES):
        print("❌ Не удалось освободить все порты. Попробуйте запустить скрипт снова или освободите порты вручную.")
        return
    
    # Проверяем порт 80 (требует root-прав)
    for name, config in services.items():
        if config["port"] == 80:
            print("⚠️  ВНИМАНИЕ: Порт 80 требует root-прав!")
            print("   Если скрипт завершится с ошибкой, запустите с sudo:\n")
            print("   sudo python3 run_mocks.py\n")
            break
    
    # Регистрируем обработчик сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Запускаем все mock-сервисы
    for name, config in services.items():
        try:
            start_service(name, config)
            time.sleep(1)  # Небольшая задержка между запусками
        except Exception as e:
            print(f"❌ Ошибка при запуске {name}: {e}")

    # Запускаем дополнительные сервисы в правильном порядке
    print("\n" + "=" * 60)
    print("🚀 Запуск дополнительных сервисов...")
    print("=" * 60)
    
    # 1. СНАЧАЛА streamlit server
    try:
        start_additional_service("streamlit_server", ADDITIONAL_SERVICES["streamlit_server"])
        time.sleep(2)  # Даём время запуститься
    except Exception as e:
        print(f"❌ Ошибка при запуске streamlit_server: {e}")
    
    # 2. ПОТОМ main agent
    try:
        start_additional_service("main_agent", ADDITIONAL_SERVICES["main_agent"])
        time.sleep(2)  # Даём время запуститься
    except Exception as e:
        print(f"❌ Ошибка при запуске main_agent: {e}")
    
    # 3. В КОНЦЕ streamlit UI
    try:
        start_additional_service("streamlit_ui", ADDITIONAL_SERVICES["streamlit_ui"])
        time.sleep(2)  # Даём время запуститься
    except Exception as e:
        print(f"❌ Ошибка при запуске streamlit_ui: {e}")

    # Освобождаем порт агента при необходимости и запускаем его
    if is_port_in_use(ADK_AGENT_PORT):
        print(f"\n⚠️  Порт {ADK_AGENT_PORT} занят. Пытаюсь освободить...")
        if kill_process_on_port(ADK_AGENT_PORT):
            time.sleep(1)
    try:
        start_adk_agent()
    except Exception as e:
        print(f"❌ Ошибка при запуске ADK агента: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Все сервисы запущены!")
    print("=" * 60)
    print("\nЗапущенные сервисы:")
    for proc_info in PROCESSES:
        print(f"  • {proc_info['name']}: http://localhost:{proc_info['port']}")
    print("\n💡 Нажмите Ctrl+C для остановки всех сервисов\n")
    
    # Мониторим процессы
    terminated_processes = set()
    try:
        while True:
            for proc_info in PROCESSES:
                proc_id = id(proc_info["process"])
                if proc_id in terminated_processes:
                    continue
                    
                if proc_info["process"].poll() is not None:
                    # Процесс завершился (ошибка или остановка)
                    terminated_processes.add(proc_id)
                    try:
                        output, _ = proc_info["process"].communicate(timeout=1)
                        if output:
                            print(f"\n❌ [{proc_info['name']}] Процесс завершился:")
                            print(output)
                            print(f"💡 Проверьте логи выше для диагностики проблемы\n")
                    except (ValueError, subprocess.TimeoutExpired):
                        # Поток уже закрыт или таймаут - игнорируем
                        pass
            
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    main()

