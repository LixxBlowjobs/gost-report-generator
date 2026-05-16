import json
from pathlib import Path
from typing import Dict, Any, Optional


class PromptBuilder:
    """Читает gost_rules.json и собирает промпты для LLM."""
    
    def __init__(self, rules_path: str = "/app/data/gost_rules.json"):
        with open(rules_path, encoding="utf-8") as f:
            self.rules = json.load(f)

    def _fmt(self, path: str, default: str = "") -> str:
        """Безопасно достаёт значение из вложенного словаря по точечному пути."""
        keys = path.split(".")
        val = self.rules
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k, {})
            else:
                return default
        return val.get("value", default) if isinstance(val, dict) else str(val)

    # ========== СИСТЕМНЫЙ ПРОМПТ ==========
    
    def get_system_prompt(self) -> str:
        return f"""Ты — опытный технический писатель, оформляющий отчёты по ГОСТ 7.32-2017.

ПРАВИЛА ОФОРМЛЕНИЯ:
- Шрифт: {self._fmt("formatting.font.main_text.typeface")}, {self._fmt("formatting.font.main_text.size")}
- Интервал: {self._fmt("formatting.spacing.main_text")}
- Абзацный отступ: {self._fmt("formatting.spacing.indent")}
- Поля: левое {self._fmt("formatting.page.margins.left")}, правое {self._fmt("formatting.page.margins.right")}, верх/низ {self._fmt("formatting.page.margins.top")}
- Выравнивание: {self._fmt("formatting.alignment.main_text")}
- Заголовки глав: ПРОПИСНЫЕ, полужирный, по центру, с новой страницы
- Заголовки подразделов: полужирный, с абзацного отступа
- Точка в конце заголовков НЕ ставится
- Таблицы: шрифт 10-12 пт, заголовок «Таблица N — Название»
- Рисунки: подпись «Рисунок N — Название» по центру
- Ссылки на источники: [1], [2, 3], [1-5]
- Стиль: академический
- Возврат: строго JSON по запрошенной схеме"""

    # ========== ВВЕДЕНИЕ ==========
    
    def build_introduction(self, topic: str, description: str, code_summary: str) -> str:
        intro = self.rules.get("structural_elements", {}).get("introduction", {})
        required = intro.get("content", intro.get("required_content", []))
        req_list = "\n".join(f"   - {r}" for r in required)
        
        return f"""Напиши раздел «ВВЕДЕНИЕ» отчёта о НИР.

Введение должно содержать:
{req_list}

Тема НИР: {topic}
Описание проекта: {description}
Анализ кода: {code_summary}

ВАЖНО: В тексте обязательно добавляй ссылки на источники из списка литературы в формате [1], [2, 3], [1-5]. Если делаешь утверждение — подкрепляй ссылкой. Количество ссылок во введении: минимум 3-5.

Верни JSON: {{"heading": "ВВЕДЕНИЕ", "paragraphs": ["абзац1", "абзац2", ...]}}"""

    # ========== ГЛАВЫ ==========
    
    def build_chapter(self, num: int, name: str, topic: str, 
                      code_summary: str, prev_summary: Optional[str] = None) -> str:
        prev = f"\nСодержание предыдущей главы: {prev_summary}" if prev_summary else ""
        
        return f"""Напиши главу {num} «{name}».{prev}

Структура — подразделы с заголовками и абзацами.

Тема: {topic}
Анализ кода: {code_summary}

ВАЖНО ПРО ТАБЛИЦЫ:
- Если в тексте нужна таблица, используй формат строк с пайпами:
  | Заголовок1 | Заголовок2 |
  | Значение1  | Значение2  |
- Каждая строка таблицы — отдельный элемент в массиве paragraphs.
- Разделитель |---| не нужен.

ВАЖНО ПРО ССЫЛКИ: В текст обязательно вставляй ссылки на источники из списка литературы в формате [1], [2, 3], [1-5]. В каждом подразделе минимум 1-2 ссылки. Пример: «Как показано в работе [1], ...»

Верни JSON: {{"heading": "{num} {name.upper()}", "subsections": [{{"heading": "{num}.1 ...", "paragraphs": ["..."]}}, ...]}}"""

    # ========== ЗАКЛЮЧЕНИЕ ==========
    
    def build_conclusion(self, tasks: str, chapters_summary: str) -> str:
        concl = self.rules.get("structural_elements", {}).get("conclusion", {})
        required = concl.get("content", concl.get("required_content", []))
        req_list = "\n".join(f"   - {r}" for r in required)
        
        return f"""Напиши раздел «ЗАКЛЮЧЕНИЕ».

Должно содержать:
{req_list}

Задачи из введения: {tasks}
Содержание глав: {chapters_summary}

ВАЖНО: Добавь ссылки на источники [1], [2, 3] в текст заключения.

Верни JSON: {{"heading": "ЗАКЛЮЧЕНИЕ", "paragraphs": ["абзац1", "абзац2", ...]}}"""

    # ========== РЕФЕРАТ ==========
    
    def build_abstract(self, summary: str) -> str:
        abstract = self.rules.get("structural_elements", {}).get("abstract", {})
        
        return f"""Напиши реферат отчёта о НИР.

Объём: до 850 знаков, 5-15 ключевых слов.

Содержание отчёта: {summary}

Верни JSON: {{"text": "текст реферата", "keywords": ["КЛЮЧЕВОЕ", "СЛОВО", ...]}}"""

    # ========== СПИСОК ЛИТЕРАТУРЫ ==========
    
    def build_references(self, topic: str, chapters_summary: str) -> str:
        refs = self.rules.get("structural_elements", {}).get("references_list", {})
        
        return f"""Сформируй список использованных источников (10-15 шт).

Порядок: {refs.get("order", "по упоминанию в тексте")}

Тема: {topic}
Содержание глав: {chapters_summary}

Оформляй по ГОСТ 7.1-2003.
Верни JSON: {{"references": ["1. ...", "2. ...", ...]}}"""

    # ========== ТЕРМИНЫ ==========

    def build_terms(self, topic: str, code_summary: str) -> str:
        terms_data = self.rules.get("terms_and_definitions", [])
        examples = "\n".join(f"  - {t['term']} — {t['definition'][:80]}..." for t in terms_data[:3])

        return f"""Сформируй перечень терминов и определений для отчёта о НИР.

Тема: {topic}
Анализ кода: {code_summary}

Примеры терминов из ГОСТ:
{examples}

Верни JSON: {{"opening": "В настоящем отчете о НИР применяют следующие термины с соответствующими определениями:", "items": [{{"term": "Термин", "definition": "определение"}}, ...]}}"""

    # ========== СОКРАЩЕНИЯ ==========

    def build_abbreviations(self, topic: str, code_summary: str) -> str:
        abbr_data = self.rules.get("abbreviations", [])
        examples = "\n".join(f"  - {a['abbreviation']} — {a['full_name']}" for a in abbr_data[:5])

        return f"""Сформируй перечень сокращений и обозначений для отчёта о НИР.

Тема: {topic}
Анализ кода: {code_summary}

Примеры сокращений из ГОСТ:
{examples}

Верни JSON: {{"opening": "В настоящем отчете о НИР применяют следующие сокращения и обозначения:", "items": [{{"abbr": "НИР", "full": "научно-исследовательская работа"}}, ...]}}"""


# Синглтон
prompt_builder = PromptBuilder()
