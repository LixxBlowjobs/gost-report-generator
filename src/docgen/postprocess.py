"""Postprocess generated text to remove AI writing patterns."""
import re

# Patterns to remove or replace, derived from avoid-ai-writing skill
# Russian and English AI-isms common in LLM output

AI_WORD_REPLACE_RU = [
    (r'\bглубоко погрузимся\b', 'рассмотрим'),
    (r'\bпогрузимся в\b', 'рассмотрим'),
    (r'\bстоит отметить,\s*что\b', ''),
    (r'\bстоит подчеркнуть,\s*что\b', ''),
    (r'\bважно отметить,\s*что\b', ''),
    (r'\bважно понимать,\s*что\b', ''),
    (r'\bследует отметить,\s*что\b', ''),
    (r'\bнеобходимо подчеркнуть,\s*что\b', ''),
    (r'\bв современном мире\b', ''),
    (r'\bв эпоху цифровизации\b', ''),
    (r'\bв наши дни\b', ''),
    (r'\bпоистине\b', ''),
    (r'\bпо-настоящему\b', ''),
    (r'\bнесомненно,?\s*', ''),
    (r'\bбезусловно,?\s*', ''),
    (r'\bочевидно,?\s*', ''),
    (r'\bбез сомнения,?\s*', ''),
    (r'\bв первую очередь\b', 'прежде всего'),
    (r'\bкомплексный\b', 'полный'),
    (r'\bкомплексное решение\b', 'полное решение'),
    (r'\bинновационный\b', 'новый'),
    (r'\bпередовой\b', 'современный'),
    (r'\bреволюционный\b', 'новый'),
    (r'\bбесшовный\b', 'плавный'),
    (r'\bбесшовно\b', 'плавно'),
    (r'\bключевой момент\b', 'момент'),
    (r'\bна сегодняшний день\b', 'сегодня'),
    (r'\bна данный момент\b', 'сейчас'),
]

AI_WORD_REPLACE_EN = [
    (r'\bdelve into\b', 'рассмотрим'),
    (r'\bdelve\b', 'изучить'),
    (r'\blandscape\b', 'область'),
    (r'\brealm\b', 'область'),
    (r'\bparadigm\b', 'подход'),
    (r'\bembark\b', 'начать'),
    (r'\btestament to\b', 'показывает'),
    (r'\brobust\b', 'надёжный'),
    (r'\bcomprehensive\b', 'полный'),
    (r'\bcutting-edge\b', 'современный'),
    (r'\bleverage\b', 'использовать'),
    (r'\bpivotal\b', 'ключевой'),
    (r'\bmeticulous\b', 'тщательный'),
    (r'\bmeticulously\b', 'тщательно'),
    (r'\bseamless\b', 'плавный'),
    (r'\bseamlessly\b', 'плавно'),
    (r'\butilize\b', 'использовать'),
    (r'\bnestled\b', 'расположен'),
    (r'\bvibrant\b', 'активный'),
    (r'\bintricate\b', 'сложный'),
    (r'\brevolutionize\b', 'изменить'),
]

# "не X — а Y", "не просто X, а Y", "не только X, но и Y" — restructure
NEGATIVE_PARALLEL_PATTERNS = [
    re.compile(r'\bне\s+просто\s+([^,—]+)[,—]\s*а\s+([^.;]+)', re.IGNORECASE),
    re.compile(r'\bне\s+только\s+([^,]+),\s*но\s+и\s+([^.;]+)', re.IGNORECASE),
]


def clean_text(text: str) -> str:
    """Remove AI-isms from a single string."""
    if not isinstance(text, str) or not text.strip():
        return text

    # Replace word-level AI-isms
    for pattern, replacement in AI_WORD_REPLACE_RU + AI_WORD_REPLACE_EN:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Restructure "не просто X, а Y" → "Y" (keeps the positive statement)
    for p in NEGATIVE_PARALLEL_PATTERNS:
        text = p.sub(r'\2', text)

    # Reduce em-dash overuse: replace em-dashes used as parenthetical with commas
    # Only do this for inline em-dash with surrounding spaces (not headings)
    # Keep one em-dash per ~1000 chars
    em_count = text.count('—')
    if em_count > max(1, len(text) // 1000):
        # Replace pairs of em-dashes with commas (parentheticals)
        # First, replace "X — Y — Z" patterns where it acts as a parenthetical
        # Conservative: replace standalone em-dashes used inline (with spaces both sides)
        # but keep dashes used as headers like "ГЛАВА 1 — Название"
        # Heuristic: if the line contains "ГЛАВА", "Таблица", "Рисунок", "Листинг", "—" — keep
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            if re.search(r'\b(ГЛАВА|Таблица|Рисунок|Листинг|Приложение)\s+\w+\s+—', line):
                cleaned_lines.append(line)
                continue
            # Replace " — " (em-dash with spaces) with ", " when there are multiple
            if line.count(' — ') > 1:
                # Keep first, replace rest with commas
                parts = line.split(' — ')
                new_line = parts[0]
                for i, p in enumerate(parts[1:]):
                    if i == 0:
                        new_line += ' — ' + p
                    else:
                        new_line += ', ' + p
                cleaned_lines.append(new_line)
            else:
                cleaned_lines.append(line)
        text = '\n'.join(cleaned_lines)

    # Clean up double spaces and leading/trailing punctuation artifacts
    text = re.sub(r'  +', ' ', text)
    text = re.sub(r'\s+,', ',', text)
    text = re.sub(r'\s+\.', '.', text)
    text = re.sub(r'^[\s,;]+', '', text)
    # Capitalize first letter if lowercase
    if text and text[0].islower():
        text = text[0].upper() + text[1:]

    return text.strip()


def clean_section(section: dict) -> dict:
    """Recursively clean strings inside a section dict."""
    if isinstance(section, dict):
        return {k: clean_section(v) for k, v in section.items()}
    elif isinstance(section, list):
        return [clean_section(item) for item in section]
    elif isinstance(section, str):
        return clean_text(section)
    return section
