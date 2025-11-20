#!/usr/bin/env python3
"""
Утилита для проверки статуса всех запущенных сервисов.
Использование: python3 check_services.py
"""
import httpx
import sys

SERVICES = {
    "ATS Service": "http://localhost:80",
    "AI Matching Service": "http://localhost:8001",
    "Calling Agent": "http://localhost:8002",
    "ADK Agent": "http://127.0.0.1:8000",
}

def check_service(name, url):
    """Проверяет доступность сервиса."""
    try:
        response = httpx.get(url, timeout=2.0, follow_redirects=True)
        if response.status_code < 500:
            return True, f"✅ {name}: работает (HTTP {response.status_code})"
        else:
            return False, f"❌ {name}: ошибка сервера (HTTP {response.status_code})"
    except httpx.ConnectError:
        return False, f"❌ {name}: не доступен (не запущен?)"
    except httpx.TimeoutException:
        return False, f"⚠️  {name}: таймаут (возможно, ещё запускается)"
    except Exception as e:
        return False, f"❌ {name}: ошибка - {str(e)}"

def main():
    print("=" * 60)
    print("🔍 Проверка статуса сервисов...")
    print("=" * 60)
    print()
    
    all_ok = True
    for name, url in SERVICES.items():
        is_ok, message = check_service(name, url)
        print(message)
        if not is_ok:
            all_ok = False
    
    print()
    print("=" * 60)
    if all_ok:
        print("✅ Все сервисы работают!")
    else:
        print("⚠️  Некоторые сервисы не доступны")
        print("💡 Убедитесь, что запущен run_mocks.py")
    print("=" * 60)
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())

