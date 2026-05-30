import os, json, time
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn, nsdecls
from docx.oxml import OxmlElement, parse_xml

from . import styles, postprocess
from .sections import abstract, terms, intro, chapter, conclusion, references, plan as plan_module


def _add_toc(doc):
    styles.make_paragraph(doc, "СОДЕРЖАНИЕ", font_size=14, bold=True,
                          alignment=WD_ALIGN_PARAGRAPH.CENTER,
                          first_line_indent=0, space_before=12, space_after=6,
                          page_break_before=True, line_spacing=1.0,
                          style='Heading 1')
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.line_spacing = 1.5
    r = p.add_run()
    fc1 = OxmlElement('w:fldChar')
    fc1.set(qn('w:fldCharType'), 'begin')
    r._r.append(fc1)
    r2 = p.add_run()
    it = OxmlElement('w:instrText')
    it.set(qn('xml:space'), 'preserve')
    it.text = ' TOC \\o "1-2" \\h '
    r2._r.append(it)
    r3 = p.add_run()
    fc2 = OxmlElement('w:fldChar')
    fc2.set(qn('w:fldCharType'), 'separate')
    r3._r.append(fc2)
    r4 = p.add_run()
    r4.font.color.rgb = RGBColor(128, 128, 128)
    r4.font.size = Pt(14)
    r4.text = "(Обновите поле после открытия в Word)"
    r5 = p.add_run()
    fc3 = OxmlElement('w:fldChar')
    fc3.set(qn('w:fldCharType'), 'end')
    r5._r.append(fc3)


def _add_abbreviations(doc, analysis: dict):
    styles.make_paragraph(doc, "СОКРАЩЕНИЯ И ОБОЗНАЧЕНИЯ", font_size=14,
                          bold=True, alignment=WD_ALIGN_PARAGRAPH.CENTER,
                          first_line_indent=0, space_before=12, space_after=6,
                          page_break_before=True, line_spacing=1.0,
                          style='Heading 1', keep_with_next=True)
    styles.make_paragraph(doc,
        "В настоящем отчёте о НИР применяют следующие сокращения и обозначения:",
        font_size=14, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY,
        first_line_indent=1.25, space_after=3, keep_with_next=True)
    abbrs = _extract_abbreviations(analysis)
    styles.add_definition_table(doc, abbrs)


def _extract_abbreviations(analysis: dict) -> list:
    tech = analysis.get("tech_stack", [])
    seen = set()
    result = []
    common = {
        "API": "Application Programming Interface (интерфейс программирования приложений)",
        "CLI": "Command Line Interface (интерфейс командной строки)",
        "HTTP": "HyperText Transfer Protocol (протокол передачи гипертекста)",
        "JSON": "JavaScript Object Notation (текстовый формат обмена данными)",
        "LLM": "Large Language Model (большая языковая модель)",
        "LOC": "Lines of Code (строки исходного кода)",
        "REST": "Representational State Transfer (архитектурный стиль)",
        "ГОСТ": "государственный стандарт",
        "НИР": "научно-исследовательская работа",
        "ПО": "программное обеспечение",
        "СУБД": "система управления базами данных",
    }
    for name in tech:
        if name in common and name not in seen:
            seen.add(name)
            result.append((name, common[name]))
    # Add common terms always if relevant
    for k, v in common.items():
        if k not in seen and k in ("НИР", "ПО", "ГОСТ", "LLM", "API"):
            seen.add(k)
            result.append((k, v))
    # Sort alphabetically (cyrillic first then latin)
    result.sort(key=lambda x: (x[0][0].isascii(), x[0]))
    return result[:14]


def _setup_document(doc):
    """Configure page, fonts, heading styles, hyperlink style."""
    # Page setup
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(3.0)
    section.right_margin = Cm(1.5)
    section.different_first_page_header_footer = True

    # Normal style
    normal = doc.styles['Normal']
    normal.font.name = 'Times New Roman'
    normal.font.size = Pt(14)
    normal.paragraph_format.line_spacing = 1.5

    # Heading styles
    for sname in ['Heading 1', 'Heading 2']:
        hs = doc.styles[sname]
        hs.font.name = 'Times New Roman'
        hs.font.color.rgb = RGBColor(0, 0, 0)
        hs.font.size = Pt(14)
        hs.font.bold = True
        hs.paragraph_format.line_spacing = 1.0
        rpr = hs.element.find(qn('w:rPr'))
        if rpr is not None:
            rFonts = rpr.find(qn('w:rFonts'))
            if rFonts is None:
                rFonts = parse_xml(f'<w:rFonts {nsdecls("w")} w:eastAsia="Times New Roman"/>')
                rpr.append(rFonts)
            else:
                rFonts.set(qn('w:eastAsia'), 'Times New Roman')

    hs1 = doc.styles['Heading 1']
    hs1.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    hs1.paragraph_format.space_before = Pt(12)
    hs1.paragraph_format.space_after = Pt(6)
    hs1.paragraph_format.first_line_indent = Cm(0)

    hs2 = doc.styles['Heading 2']
    hs2.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    hs2.paragraph_format.space_before = Pt(6)
    hs2.paragraph_format.space_after = Pt(3)
    hs2.paragraph_format.first_line_indent = Cm(1.25)

    # Hyperlink style
    try:
        hl_style = doc.styles['Hyperlink']
    except KeyError:
        hl_style = doc.styles.add_style('Hyperlink', 2)
    hl_style.font.color.rgb = RGBColor(0, 0, 0)
    hl_style.font.underline = False


def _build_title_page(doc, meta: dict):
    for _ in range(3):
        styles.make_paragraph(doc, "", font_size=14, space_before=0, space_after=0)

    styles.make_paragraph(doc, "МИНИСТЕРСТВО НАУКИ И ВЫСШЕГО ОБРАЗОВАНИЯ РОССИЙСКОЙ ФЕДЕРАЦИИ",
                          font_size=14, alignment=WD_ALIGN_PARAGRAPH.CENTER,
                          first_line_indent=0, space_after=0, line_spacing=1.0)
    styles.make_paragraph(doc,
                          "ФЕДЕРАЛЬНОЕ ГОСУДАРСТВЕННОЕ БЮДЖЕТНОЕ ОБРАЗОВАТЕЛЬНОЕ УЧРЕЖДЕНИЕ ВЫСШЕГО ОБРАЗОВАНИЯ",
                          font_size=14, alignment=WD_ALIGN_PARAGRAPH.CENTER,
                          first_line_indent=0, space_after=0, line_spacing=1.0)
    styles.make_paragraph(doc, f'«{meta.get("university", "ПРИМЕРНЫЙ УНИВЕРСИТЕТ").upper()}»',
                          font_size=14, alignment=WD_ALIGN_PARAGRAPH.CENTER,
                          first_line_indent=0, space_after=0, line_spacing=1.0)

    for _ in range(4):
        styles.make_paragraph(doc, "", font_size=14, space_before=0, space_after=0)

    styles.make_paragraph(doc, "ОТЧЁТ О НАУЧНО-ИССЛЕДОВАТЕЛЬСКОЙ РАБОТЕ", font_size=14,
                          bold=True, alignment=WD_ALIGN_PARAGRAPH.CENTER,
                          first_line_indent=0, space_after=0, line_spacing=1.5)
    styles.make_paragraph(doc, meta.get("topic", ""), font_size=14,
                          alignment=WD_ALIGN_PARAGRAPH.CENTER,
                          first_line_indent=0, space_after=0, line_spacing=1.5)
    styles.make_paragraph(doc, "(заключительный)", font_size=14,
                          alignment=WD_ALIGN_PARAGRAPH.CENTER,
                          first_line_indent=0, space_after=0, line_spacing=1.5)

    for _ in range(4):
        styles.make_paragraph(doc, "", font_size=14, space_before=0, space_after=0)

    student = meta.get("student_name", "")
    if student:
        styles.make_paragraph(doc, f"Исполнитель: {student}", font_size=14,
                              alignment=WD_ALIGN_PARAGRAPH.LEFT,
                              first_line_indent=0, space_after=0, line_spacing=1.5)
    supervisor = meta.get("supervisor", "")
    if supervisor:
        styles.make_paragraph(doc, f"Руководитель: {supervisor}", font_size=14,
                              alignment=WD_ALIGN_PARAGRAPH.LEFT,
                              first_line_indent=0, space_after=0, line_spacing=1.5)

    for _ in range(3):
        styles.make_paragraph(doc, "", font_size=14, space_before=0, space_after=0)

    styles.make_paragraph(doc, f"Москва {meta.get('year', 2026)}", font_size=14,
                          alignment=WD_ALIGN_PARAGRAPH.CENTER,
                          first_line_indent=0, space_after=0, line_spacing=1.5)


def build_report(analysis: dict, metadata: dict, output_path: str,
                 analysis_path: str = None, skip_postprocess: bool = False) -> str:
    log_lines = []

    def log(msg):
        log_lines.append(msg)
        print(f"  {msg}")

    t_start = time.time()
    doc = Document()
    styles.reset_counters()

    default_meta = {
        "topic": "Разработка системы генерации отчётов",
        "student_name": "Студент И. И.",
        "group": "ИВТ-41",
        "supervisor": "Руководитель И. И.",
        "university": "Примерный университет",
        "year": 2026,
        "description": "",
    }
    if metadata:
        default_meta.update(metadata)
    meta = default_meta

    _setup_document(doc)
    styles.add_page_numbers(doc)

    # ── Stage 1: Plan ──
    log("План — генерация...")
    try:
        plan = plan_module.generate(analysis, meta)
        log(f"План OK ({len(plan.get('chapters', []))} глав, "
            f"{len(plan.get('reference_topics', []))} тем источников)")
    except Exception as e:
        log(f"План: {e} (используются заглушки)")
        plan = plan_module.generate({}, {})

    # ── Stage 2: References (so chapters can cite them) ──
    log("Литература — генерация...")
    refs_result = None
    refs_list = []
    try:
        refs_result = references.generate(analysis, meta, plan)
        refs_list = refs_result.get("references", [])
        log(f"Литература OK ({len(refs_list)} источников)")
    except Exception as e:
        log(f"Литература: {e}")
        refs_result = {"references": []}

    # ── Stage 3: Introduction ──
    log("Введение — генерация...")
    intro_result = None
    try:
        intro_result = intro.generate(analysis, meta, plan)
        log("Введение OK")
    except Exception as e:
        log(f"Введение: {e}")
        intro_result = {"paragraphs": []}

    # ── Stage 4: Chapters ──
    chapter_results = {}
    total_counts = {"figures": 0, "tables": 0, "listings": 0}
    chapters_plan = plan.get("chapters", [])
    for ch_plan in chapters_plan:
        ch_num = ch_plan.get("num", 1)
        log(f"Глава {ch_num} — генерация...")
        try:
            ch_result = chapter.generate(analysis, meta, ch_num, ch_plan, refs_list)
            chapter_results[ch_num] = ch_result
            log(f"Глава {ch_num} OK ({len(ch_result.get('sections', []))} подразделов)")
        except Exception as e:
            log(f"Глава {ch_num}: {e}")
            chapter_results[ch_num] = {"sections": []}

    # ── Stage 5: Conclusion ──
    log("Заключение — генерация...")
    conc_result = None
    try:
        conc_result = conclusion.generate(analysis, meta, plan)
        log("Заключение OK")
    except Exception as e:
        log(f"Заключение: {e}")
        conc_result = {"paragraphs": []}

    # ── Stage 6: Terms ──
    log("Термины — генерация...")
    terms_result = None
    try:
        terms_result = terms.generate(analysis, meta)
        log("Термины OK")
    except Exception as e:
        log(f"Термины: {e}")
        terms_result = {"terms": []}

    # ── Stage 7: Abstract (last, knows real counts) ──
    log("Реферат — генерация...")
    # Pre-count figures/tables/listings from chapter results
    for ch_result in chapter_results.values():
        for sec in ch_result.get("sections", []):
            total_counts["tables"] += len(sec.get("tables", []))
            total_counts["figures"] += len(sec.get("figures", []))
            total_counts["listings"] += len(sec.get("listings", []))
    counts = {
        "pages": 30,
        "figures": total_counts["figures"] or 8,
        "tables": total_counts["tables"] or 6,
        "sources": len(refs_list) or 12,
        "apps": 0,
    }
    ab_result = None
    try:
        ab_result = abstract.generate(analysis, meta, counts)
        log("Реферат OK")
    except Exception as e:
        log(f"Реферат: {e}")
        ab_result = {"volume": "", "keywords": [], "text": ""}

    # ── Stage 8: Postprocessing (avoid-ai-writing) ──
    if not skip_postprocess:
        log("Постобработка (avoid-ai-writing)...")
        ab_result = postprocess.clean_section(ab_result)
        intro_result = postprocess.clean_section(intro_result)
        for k in list(chapter_results.keys()):
            chapter_results[k] = postprocess.clean_section(chapter_results[k])
        conc_result = postprocess.clean_section(conc_result)
        # Note: references and terms are factual, don't clean
        log("Постобработка OK")

    # ── Stage 9: Build DOCX ──
    log("Сборка DOCX...")
    _build_title_page(doc, meta)

    # Abstract
    abstract.build(doc, ab_result, styles)

    # TOC
    _add_toc(doc)

    # Terms
    terms.build(doc, terms_result, styles)

    # Abbreviations
    _add_abbreviations(doc, analysis)

    # Introduction
    intro.build(doc, intro_result, styles)

    # Chapters
    for ch_plan in chapters_plan:
        ch_num = ch_plan.get("num", 1)
        ch_name = ch_plan.get("name", "")
        heading = f"ГЛАВА {ch_num} — {ch_name}"
        styles.make_paragraph(doc, heading,
                              font_size=14, bold=True,
                              alignment=WD_ALIGN_PARAGRAPH.CENTER,
                              first_line_indent=0, space_before=12, space_after=6,
                              page_break_before=True, line_spacing=1.0,
                              style='Heading 1')
        ch_result = chapter_results.get(ch_num, {})
        chapter.build(doc, ch_result, styles)

    # Conclusion
    conclusion.build(doc, conc_result, styles)

    # References
    references.build(doc, refs_result, styles)

    doc.save(output_path)
    log("Сборка OK")

    elapsed = time.time() - t_start
    log(f"Готово: {output_path} ({elapsed:.0f} сек)")
    log(f"Размер: {os.path.getsize(output_path)} байт")

    if analysis_path:
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump({"analysis": analysis, "plan": plan}, f,
                      indent=2, ensure_ascii=False)
        log(f"Анализ + план: {analysis_path}")

    return "\n".join(log_lines)
