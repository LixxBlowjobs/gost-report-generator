import json
from docx.enum.text import WD_ALIGN_PARAGRAPH
from ..llm import generate_json
from ..config import SECTION_PROMPTS


def generate(analysis: dict, metadata: dict, plan: dict = None) -> dict:
    user = SECTION_PROMPTS["references"].format(
        analysis=json.dumps(analysis, indent=2, ensure_ascii=False),
        reference_topics=json.dumps((plan or {}).get("reference_topics", []),
                                    ensure_ascii=False),
    )
    return generate_json(SECTION_PROMPTS["references"], user,
                         max_tokens=3072, label="Литература")


def build(doc, result: dict, styles):
    styles.make_paragraph(doc, "СПИСОК ЛИТЕРАТУРЫ", font_size=14, bold=True,
                          alignment=WD_ALIGN_PARAGRAPH.CENTER,
                          first_line_indent=0, space_before=12, space_after=6,
                          page_break_before=True, line_spacing=1.0,
                          style='Heading 1')
    for ref in result.get("references", []):
        styles.add_reference(doc, ref)
