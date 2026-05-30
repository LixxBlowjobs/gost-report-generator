import json

from docx.enum.text import WD_ALIGN_PARAGRAPH

from ..llm import generate_json


PROMPT = """По данным анализа проекта сгенерируй список терминов и определений (6-10 шт.) для отчёта о НИР.

Данные анализа:
{analysis}

Метаданные:
{metadata}

Верни JSON строго без markdown:
{{
  "terms": [
    ["Термин", "определение"],
    ["Термин2", "определение2"]
  ]
}}"""


def generate(analysis: dict, metadata: dict) -> dict:
    user = PROMPT.format(
        analysis=json.dumps(analysis, indent=2, ensure_ascii=False),
        metadata=json.dumps(metadata, indent=2, ensure_ascii=False),
    )
    return generate_json(PROMPT, user, max_tokens=2048, label="Термины")


def build(doc, result: dict, styles):
    styles.make_paragraph(doc, "ТЕРМИНЫ И ОПРЕДЕЛЕНИЯ", font_size=14, bold=True,
                          alignment=WD_ALIGN_PARAGRAPH.CENTER,
                          first_line_indent=0, space_before=12, space_after=6,
                          page_break_before=True, line_spacing=1.0,
                          style='Heading 1', keep_with_next=True)
    styles.make_paragraph(doc,
        "В настоящем отчёте о НИР применяют следующие термины с соответствующими определениями:",
        font_size=14, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY,
        first_line_indent=1.25, space_after=0, keep_with_next=True)
    styles.add_definition_table(doc, result.get("terms", []))
