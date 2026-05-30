import json
from docx.enum.text import WD_ALIGN_PARAGRAPH
from ..llm import generate_json
from ..config import CHAPTER_PROMPT


def _format_plan(chapter_plan: dict) -> str:
    lines = []
    for sub in chapter_plan.get("subsections", []):
        lines.append(f"\n{sub['num']} {sub['heading']}")
        for t in sub.get("thesis", []):
            lines.append(f"  - {t}")
        flags = []
        if sub.get("needs_table"):
            flags.append("таблица")
        if sub.get("needs_figure"):
            flags.append("рисунок")
        if sub.get("needs_code"):
            flags.append("листинг кода")
        if flags:
            lines.append(f"  [требуется: {', '.join(flags)}]")
        if sub.get("ref_topics"):
            lines.append(f"  [темы ссылок: {', '.join(sub['ref_topics'])}]")
    return "\n".join(lines)


def generate(analysis: dict, metadata: dict, chapter_num: int,
             chapter_plan: dict, references: list) -> dict:
    refs_str = "\n".join(references[:15]) if references else ""
    first_sub = chapter_plan.get("subsections", [{}])[0]
    first_sub_heading = f"{first_sub.get('num', '')} {first_sub.get('heading', '')}"
    plan_str = _format_plan(chapter_plan)
    chapter_name = chapter_plan.get("name", f"ГЛАВА {chapter_num}")

    user = CHAPTER_PROMPT.format(
        chapter_num=chapter_num,
        chapter_name=chapter_name,
        analysis=json.dumps(analysis, indent=2, ensure_ascii=False),
        metadata=json.dumps(metadata, indent=2, ensure_ascii=False),
        plan=plan_str,
        references=refs_str,
        first_subsection_heading=first_sub_heading,
    )
    result = generate_json(CHAPTER_PROMPT, user, max_tokens=8192,
                           label=f"Глава {chapter_num}")

    # Sanity check: each subsection from plan must be in result.sections
    plan_subs = chapter_plan.get("subsections", [])
    result_secs = result.get("sections", [])
    if len(result_secs) < len(plan_subs):
        # Fill missing subsections with placeholder
        existing_headings = {s.get("heading", "")[:6] for s in result_secs}
        for sub in plan_subs:
            sub_key = f"{sub.get('num', '')}"
            if sub_key not in existing_headings:
                result_secs.append({
                    "heading": f"{sub.get('num', '')} {sub.get('heading', '')}",
                    "paragraphs": [
                        f"В данном подразделе рассматривается {sub.get('heading', '').lower()}. "
                        f"{'; '.join(sub.get('thesis', []))}."
                    ],
                    "tables": [],
                    "figures": [],
                    "listings": [],
                })
        result["sections"] = result_secs

    return result


def build(doc, result: dict, styles, fig_offset=0, tbl_offset=0, lst_offset=0):
    """Build chapter content. Returns dict with counts for global numbering."""
    sections = result.get("sections", [])
    counts = {"figures": 0, "tables": 0, "listings": 0}
    for sec in sections:
        h = sec.get("heading", "")
        if h:
            styles.make_paragraph(doc, h, font_size=14, bold=True,
                                  alignment=WD_ALIGN_PARAGRAPH.LEFT,
                                  first_line_indent=1.25, space_before=6,
                                  space_after=3, line_spacing=1.0,
                                  style='Heading 2')
        for text in sec.get("paragraphs", []):
            if text.strip():
                styles.make_paragraph(doc, text, first_line_indent=1.25,
                                      space_after=0, line_spacing=1.5)
        for tbl in sec.get("tables", []):
            styles.make_table(doc, tbl.get("caption", ""),
                              tbl.get("headers", []),
                              tbl.get("rows", []))
            counts["tables"] += 1
        for fig in sec.get("figures", []):
            styles.make_figure(doc, fig.get("caption", ""),
                               fig.get("comment"))
            counts["figures"] += 1
        for lst in sec.get("listings", []):
            caption = lst.get("caption", "")
            code = lst.get("code", "")
            styles.make_code_block(doc, code, caption_text=caption)
            counts["listings"] += 1
    return counts
