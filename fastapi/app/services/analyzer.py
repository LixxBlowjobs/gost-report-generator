import re
from typing import Dict, Any, List

def analyze_code(source_code: str) -> Dict[str, Any]:
    """Анализирует исходный код: определяет язык, функции, классы, LOC."""
    
    language = detect_language(source_code)
    lines = source_code.split('\n')
    loc = len([l for l in lines if l.strip() and not l.strip().startswith('#') and not l.strip().startswith('//')])
    functions = find_functions(source_code, language)
    classes = find_classes(source_code, language)
    files = detect_files(source_code)
    
    return {
        "language": language,
        "files_detected": files,
        "functions": functions[:20],
        "classes": classes[:20],
        "loc": loc,
        "total_lines": len(lines)
    }

def detect_language(code: str) -> str:
    if re.search(r'\bdef\b|\bclass\b|import\s+\w+', code):
        return "Python"
    elif re.search(r'\bfunction\b|\bconst\b|\blet\b|\bvar\b|=>', code):
        return "JavaScript/TypeScript"
    elif re.search(r'\bpublic\s+class\b|\bimport\s+java\.', code):
        return "Java"
    elif re.search(r'#include|int\s+main\b', code):
        return "C/C++"
    elif re.search(r'\bpackage\s+main\b|func\s+\w+\(', code):
        return "Go"
    return "Unknown"

def find_functions(code: str, lang: str) -> List[str]:
    functions = []
    if lang == "Python":
        matches = re.finditer(r'^\s*def\s+(\w+)\s*\(', code, re.MULTILINE)
        functions = [m.group(1) for m in matches]
    elif lang == "JavaScript/TypeScript":
        matches = re.finditer(r'function\s+(\w+)\s*\(', code)
        functions = [m.group(1) for m in matches]
        arrow_matches = re.finditer(r'(?:const|let|var)\s+(\w+)\s*=\s*\(.*\)\s*=>', code)
        functions += [m.group(1) for m in arrow_matches]
    elif lang == "Java":
        matches = re.finditer(r'(?:public|private|protected|static)\s+\w+\s+(\w+)\s*\(', code)
        functions = [m.group(1) for m in matches if m.group(1) != 'class']
    elif lang == "Go":
        matches = re.finditer(r'func\s+(?:\(.*\)\s+)?(\w+)\s*\(', code)
        functions = [m.group(1) for m in matches]
    return list(set(functions))

def find_classes(code: str, lang: str) -> List[str]:
    classes = []
    if lang == "Python":
        matches = re.finditer(r'^\s*class\s+(\w+)\s*[(:]', code, re.MULTILINE)
        classes = [m.group(1) for m in matches]
    elif lang == "JavaScript/TypeScript":
        matches = re.finditer(r'class\s+(\w+)', code)
        classes = [m.group(1) for m in matches]
    elif lang == "Java":
        matches = re.finditer(r'(?:public|private)?\s*class\s+(\w+)', code)
        classes = [m.group(1) for m in matches]
    return classes

def detect_files(code: str) -> List[str]:
    files = re.findall(r'#\s*file:\s*(\S+)', code)
    if not files:
        if code.strip():
            files = ["source_code.txt"]
    return files
