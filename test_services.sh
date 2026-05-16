#!/bin/bash
BASE="http://localhost:8000/api"

echo "=== 1. HEALTH CHECK ==="
curl -s $BASE/health | python3 -m json.tool

echo -e "\n=== 2. ANALYZE (реальный код) ==="
JOB=$(curl -s -X POST $BASE/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "metadata": {
      "topic": "Калькулятор",
      "student_name": "Иванов И.И.",
      "group": "ИВТ-41",
      "supervisor": "Петров П.П.",
      "university": "МГТУ",
      "year": 2026
    },
    "source_code": "# file: calculator.py\nclass Calculator:\n    def add(self, a, b):\n        return a + b\n    \n    def subtract(self, a, b):\n        return a - b\n    \n    def multiply(self, a, b):\n        return a * b\n\n# file: utils.py\ndef factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n-1)\n\ndef fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)"
  }')
echo "$JOB" | python3 -m json.tool
JOB_ID=$(echo "$JOB" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")

echo -e "\n=== 3. GENERATE ==="
for s in introduction chapter1 chapter2 chapter3 conclusion abstract references; do
  echo "--- $s ---"
  curl -s -X POST $BASE/generate/$s \
    -H "Content-Type: application/json" \
    -d "{\"job_id\": \"$JOB_ID\"}" | python3 -m json.tool
done

echo -e "\n=== 4. BUILD ==="
curl -s -X POST $BASE/build-docx \
  -H "Content-Type: application/json" \
  -d "{\"job_id\": \"$JOB_ID\"}" | python3 -m json.tool

echo -e "\n✅ Тесты завершены. job_id: $JOB_ID"
