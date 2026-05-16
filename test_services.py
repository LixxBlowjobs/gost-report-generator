"""
Тестирование сервисов FastAPI по отдельности.
Запуск: python3 test_services.py
"""
import requests
import json
import uuid

BASE = "http://localhost:8000/api"

def test_health():
    print("\n=== 1. HEALTH CHECK ===")
    r = requests.get(f"{BASE}/health")
    print(f"Статус: {r.status_code}")
    print(f"Ответ: {r.json()}")

def test_analyze():
    print("\n=== 2. ANALYZE ===")
    payload = {
        "metadata": {
            "topic": "Тестовая тема НИР",
            "student_name": "Иванов И.И.",
            "group": "ИВТ-41",
            "supervisor": "Петров П.П.",
            "university": "МГТУ им. Баумана",
            "year": 2026
        },
        "source_code": """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

class Calculator:
    def add(self, a, b):
        return a + b
    
    def multiply(self, a, b):
        return a * b

def main():
    calc = Calculator()
    print(calc.add(2, 3))
    print(factorial(5))

if __name__ == "__main__":
    main()
""",
        "description": "Библиотека для математических вычислений"
    }
    r = requests.post(f"{BASE}/analyze", json=payload)
    print(f"Статус: {r.status_code}")
    result = r.json()
    print(f"job_id: {result.get('job_id')}")
    print(f"code_summary: {json.dumps(result.get('code_summary'), indent=2, ensure_ascii=False)}")
    return result.get('job_id')

def test_generate(job_id, section):
    print(f"\n=== 3. GENERATE /{section} ===")
    payload = {"job_id": job_id, "section": section}
    r = requests.post(f"{BASE}/generate/{section}", json=payload)
    print(f"Статус: {r.status_code}")
    print(f"Ответ: {json.dumps(r.json(), indent=2, ensure_ascii=False)}")

def test_build(job_id):
    print(f"\n=== 4. BUILD DOCX ===")
    payload = {"job_id": job_id}
    r = requests.post(f"{BASE}/build-docx", json=payload)
    print(f"Статус: {r.status_code}")
    print(f"Ответ: {json.dumps(r.json(), indent=2, ensure_ascii=False)}")

def test_download(job_id):
    print(f"\n=== 5. DOWNLOAD ===")
    r = requests.get(f"{BASE}/download/{job_id}")
    print(f"Статус: {r.status_code}")
    if r.status_code == 200:
        with open(f"/tmp/test_report_{job_id[:8]}.docx", "wb") as f:
            f.write(r.content)
        print(f"Файл сохранён: /tmp/test_report_{job_id[:8]}.docx ({len(r.content)} байт)")

if __name__ == "__main__":
    test_health()
    job_id = test_analyze()
    
    # Тестируем генерацию всех разделов
    for section in ["introduction", "chapter1", "chapter2", "chapter3", "conclusion", "abstract", "references"]:
        test_generate(job_id, section)
    
    test_build(job_id)
    test_download(job_id)
    
    print(f"\n✅ Тестирование завершено. job_id: {job_id}")
