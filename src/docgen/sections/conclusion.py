import json
from docx.enum.text import WD_ALIGN_PARAGRAPH
from ..llm import generate_json
from ..config import SECTION_PROMPTS


def generate(analysis: dict, metadata: dict, plan: dict = None) -> dict:
    user = SECTION_PROMPTS["conclusion"].format(
        analysis=json.dumps(analysis, indent=2, ensure_ascii=False),
        metadata=json.dumps(metadata, indent=2, ensure_ascii=False),
        conclusion_thesis=json.dumps((plan or {}).get("conclusion_thesis", []),
                                     ensure_ascii=False),
    )
    return generate_json(SECTION_PROMPTS["conclusion"], user,
                         max_tokens=2048, label="Заключение")


def build(doc, result: dict, styles):
    styles.make_paragraph(doc, "ЗАКЛЮЧЕНИЕ", font_size=14, bold=True,
                          alignment=WD_ALIGN_PARAGRAPH.CENTER,
                          first_line_indent=0, space_before=12, space_after=6,
                          page_break_before=True, line_spacing=1.0,
                          style='Heading 1')
    for text in result.get("paragraphs", []):
        if text.strip():
            styles.make_paragraph(doc, text, first_line_indent=1.25,
                                  space_after=0, line_spacing=1.5)
