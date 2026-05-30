import json
from ..llm import generate_json
from ..config import PLAN_PROMPT


def generate(analysis: dict, metadata: dict) -> dict:
    user = PLAN_PROMPT.format(
        analysis=json.dumps(analysis, indent=2, ensure_ascii=False),
        metadata=json.dumps(metadata, indent=2, ensure_ascii=False),
    )
    result = generate_json(PLAN_PROMPT, user, max_tokens=4096, label="План")
    # Sanity check: ensure we have 3 chapters
    chapters = result.get("chapters", [])
    if len(chapters) < 3:
        # Pad with defaults
        defaults = [
            {"num": 1, "name": "АНАЛИЗ ПРЕДМЕТНОЙ ОБЛАСТИ",
             "subsections": [
                 {"num": "1.1", "heading": "Обзор существующих решений",
                  "thesis": ["обзор инструментов", "сравнение"],
                  "needs_table": True, "needs_figure": True, "needs_code": False,
                  "ref_topics": ["обзор предметной области"]},
                 {"num": "1.2", "heading": "Требования к системе",
                  "thesis": ["функциональные", "нефункциональные"],
                  "needs_table": True, "needs_figure": False, "needs_code": False,
                  "ref_topics": ["требования к ПО"]},
                 {"num": "1.3", "heading": "Архитектурные решения",
                  "thesis": ["обоснование выбора"],
                  "needs_table": False, "needs_figure": True, "needs_code": False,
                  "ref_topics": ["архитектура ПО"]},
             ]},
            {"num": 2, "name": "ПРОЕКТИРОВАНИЕ СИСТЕМЫ",
             "subsections": [
                 {"num": "2.1", "heading": "Общая архитектура",
                  "thesis": ["компоненты", "взаимодействие"],
                  "needs_table": True, "needs_figure": True, "needs_code": False,
                  "ref_topics": ["проектирование ПО"]},
                 {"num": "2.2", "heading": "Описание модулей",
                  "thesis": ["назначение модулей", "ключевые функции"],
                  "needs_table": True, "needs_figure": False, "needs_code": True,
                  "ref_topics": ["модульная архитектура"]},
                 {"num": "2.3", "heading": "Схема данных",
                  "thesis": ["структуры данных", "обмен"],
                  "needs_table": False, "needs_figure": True, "needs_code": True,
                  "ref_topics": ["структуры данных"]},
             ]},
            {"num": 3, "name": "РЕАЛИЗАЦИЯ И ТЕСТИРОВАНИЕ",
             "subsections": [
                 {"num": "3.1", "heading": "Используемые технологии",
                  "thesis": ["стек", "обоснование"],
                  "needs_table": True, "needs_figure": False, "needs_code": False,
                  "ref_topics": ["технологии разработки"]},
                 {"num": "3.2", "heading": "Реализация ключевых модулей",
                  "thesis": ["реализация модуля 1", "реализация модуля 2"],
                  "needs_table": False, "needs_figure": False, "needs_code": True,
                  "ref_topics": ["реализация ПО"]},
                 {"num": "3.3", "heading": "Тестирование",
                  "thesis": ["виды тестов", "результаты"],
                  "needs_table": True, "needs_figure": False, "needs_code": False,
                  "ref_topics": ["тестирование ПО"]},
             ]},
        ]
        result["chapters"] = defaults

    if not result.get("intro_thesis"):
        result["intro_thesis"] = [
            "актуальность темы автоматизации генерации документов",
            "состояние проблемы и существующие решения",
            "цель работы",
            "задачи: анализ, проектирование, реализация, тестирование",
            "объект и предмет исследования",
        ]
    if not result.get("conclusion_thesis"):
        result["conclusion_thesis"] = [
            "что сделано в рамках работы",
            "полученные результаты",
            "перспективы развития",
        ]
    if not result.get("reference_topics"):
        result["reference_topics"] = [
            "ГОСТ 7.32-2017", "ГОСТ 7.1-2003", "документация Python",
            "большие языковые модели", "автоматизация документооборота",
        ]
    return result
