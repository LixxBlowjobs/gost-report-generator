import json
from docx.enum.text import WD_ALIGN_PARAGRAPH
from ..llm import generate_json
from ..config import SECTION_PROMPTS


def generate(analysis: dict, metadata: dict, counts: dict = None) -> dict:
    c = counts or {}
    user = SECTION_PROMPTS["abstract"].format(
        analysis=json.dumps(analysis, indent=2, ensure_ascii=False),
        metadata=json.dumps(metadata, indent=2, ensure_ascii=False),
        n_pages=c.get("pages", 30),
        n_figures=c.get("figures", 8),
        n_tables=c.get("tables", 6),
        n_sources=c.get("sources", 12),
        n_apps=c.get("apps", 0),
    )
    return generate_json(SECTION_PROMPTS["abstract"], user,
                         max_tokens=2048, label="Реферат")


def build(doc, result: dict, styles):
    styles.make_paragraph(doc, "РЕФЕРАТ", font_size=14, bold=True,
                          alignment=WD_ALIGN_PARAGRAPH.CENTER,
                          first_line_indent=0, space_before=12, space_after=6,
                          page_break_before=True, line_spacing=1.0)
    styles.make_paragraph(doc, result.get("volume", ""),
                          first_line_indent=0, space_after=0, line_spacing=1.5)
    kw = ", ".join(result.get("keywords", []))
    styles.make_paragraph(doc, kw.upper(), first_line_indent=0,
                          space_after=0, line_spacing=1.5)
    styles.make_paragraph(doc, result.get("text", ""),
                          first_line_indent=1.25, space_after=0,
                          line_spacing=1.5)
