import json

from ..llm import generate_json
from ..config import ANALYZER_PROMPT


def analyze(scanner_result: dict) -> dict:
    user_prompt = (
        f"Дерево проекта:\n{scanner_result['tree']}\n\n"
        f"Конфигурационные файлы:\n{json.dumps(scanner_result['configs'], indent=2, ensure_ascii=False)}\n\n"
        f"Ключевые файлы ({len(scanner_result['top_source_files'])} шт.):\n"
    )
    for path, content in scanner_result["top_source_files"].items():
        clines = content.strip().split("\n")
        if len(clines) > 80:
            content = "\n".join(clines[:80]) + "\n... (усечено)"
        user_prompt += f"\n--- {path} ---\n{content}\n"

    result = generate_json(ANALYZER_PROMPT, user_prompt,
                           max_tokens=4096, label="Анализ проекта")
    result["total_files"] = scanner_result["total_files"]
    result["total_size_kb"] = scanner_result["total_size_kb"]
    return result
