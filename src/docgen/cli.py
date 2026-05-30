#!/usr/bin/env python3
import os, sys, json, argparse, time
from datetime import datetime

from .analyzer.scanner import scan_project
from .analyzer.llm_analyzer import analyze
from .report import build_report


BANNER = r"""
╔══════════════════════════════════════════════╗
║        GOST Report Generator                 ║
║    Генерация отчётов о НИР по ГОСТ 7.32      ║
╚══════════════════════════════════════════════╝
"""


def _fmt_size(b: int) -> str:
    if b < 1024:
        return f"{b} B"
    if b < 1024 * 1024:
        return f"{b/1024:.1f} KB"
    return f"{b/1024/1024:.1f} MB"


def _load_env_file(path: str = ".env") -> None:
    """Read KEY=VALUE pairs from a .env file into os.environ."""
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


def main() -> None:
    _load_env_file()

    parser = argparse.ArgumentParser(
        prog="docgen",
        description="Генератор отчётов о НИР по ГОСТ 7.32-2017",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  %(prog)s -p /path/to/project -o report.docx
  %(prog)s -p /path/to/project -o report.docx -m meta.json
  %(prog)s -p /path/to/project --analyze-only
  %(prog)s -p /path/to/project -o report.docx -a cached_analysis.json
""",
    )
    parser.add_argument("-p", "--project", required=True,
                        help="Путь к анализируемому проекту")
    parser.add_argument("-o", "--output", default="report.docx",
                        help="Путь для сохранения DOCX")
    parser.add_argument("-m", "--metadata",
                        help="JSON-файл с метаданными (тема, ФИО, ВУЗ)")
    parser.add_argument("-a", "--analysis",
                        help="Готовый JSON анализа (вместо нового LLM-вызова)")
    parser.add_argument("--save-analysis",
                        help="Куда сохранить результаты анализа (JSON)")
    parser.add_argument("--skip-llm", action="store_true",
                        help="Не вызывать LLM (только сканирование)")
    parser.add_argument("--analyze-only", action="store_true",
                        help="Только анализ, без генерации DOCX")
    parser.add_argument("--no-postprocess", action="store_true",
                        help="Не запускать avoid-ai-writing постобработку")
    parser.add_argument("--api-key",
                        help="OpenRouter API ключ (или OPENROUTER_API_KEY)")

    args = parser.parse_args()
    print(BANNER)

    # ── API key ──
    if args.api_key:
        os.environ["OPENROUTER_API_KEY"] = args.api_key
    has_key = bool(os.environ.get("OPENROUTER_API_KEY", ""))
    if not has_key and not args.skip_llm:
        print("  ! OPENROUTER_API_KEY не задан — переход в --skip-llm")
        args.skip_llm = True

    if not os.path.isdir(args.project):
        print(f"  ✗ Путь не найден: {args.project}")
        sys.exit(1)

    if not args.save_analysis:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.save_analysis = f"analysis_{ts}.json"

    print(f"  Проект:  {args.project}")
    print(f"  Анализ:  {'LLM' if not args.skip_llm else 'только сканирование'}")
    print(f"  Отчёт:   {args.output}")
    print(f"  " + "─" * 50)
    print()

    t_start = time.time()

    # ── Stage 1: scan ──
    print("  [1/3] Сканирование проекта...", end=" ", flush=True)
    t = time.time()
    try:
        scan = scan_project(args.project)
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)
    print(f"OK ({time.time()-t:.1f}s, {scan.get('total_files', 0)} "
          f"файлов, {scan.get('total_size_kb', 0)} KB)")

    # ── Stage 2: LLM analysis (or load cached) ──
    analysis = None
    if args.analysis:
        print(f"  [2/3] Загрузка анализа из {args.analysis}...", end=" ",
              flush=True)
        try:
            with open(args.analysis, encoding="utf-8") as f:
                analysis = json.load(f)
            print("OK")
        except Exception as e:
            print(f"FAIL: {e}")
            sys.exit(1)
    elif not args.skip_llm:
        print("  [2/3] LLM-анализ...")
        t = time.time()
        try:
            analysis = analyze(scan)
            print(f"        OK ({time.time()-t:.1f}s)")
            print(f"        Проект:     {analysis.get('project_name', '?')}")
            print(f"        Назначение: {analysis.get('purpose', '?')}")
            tech = ", ".join(analysis.get("tech_stack", [])[:8])
            print(f"        Технологии: {tech}")
        except Exception as e:
            print(f"        FAIL: {e}")
            print("        Переход в режим --skip-llm.")
            args.skip_llm = True

    if args.analyze_only:
        if analysis:
            with open(args.save_analysis, "w", encoding="utf-8") as f:
                json.dump(analysis, f, indent=2, ensure_ascii=False)
            print(f"  Анализ сохранён: {args.save_analysis}")
        print(f"\n  Готово за {time.time()-t_start:.1f} сек.")
        return

    # ── Stage 3: build report ──
    metadata = {}
    if args.metadata:
        try:
            with open(args.metadata, encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception as e:
            print(f"  ! Не удалось загрузить метаданные: {e}")

    print(f"  [3/3] Генерация отчёта...")
    try:
        build_report(
            analysis or scan,
            metadata,
            args.output,
            analysis_path=args.save_analysis if analysis else None,
            skip_postprocess=args.no_postprocess,
        )
    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    elapsed = time.time() - t_start
    if os.path.exists(args.output):
        print()
        print("  " + "=" * 50)
        print(f"  Результат: {args.output} ({_fmt_size(os.path.getsize(args.output))})")
        print(f"  Время:     {elapsed:.1f} сек")
        print("  " + "=" * 50)


if __name__ == "__main__":
    main()
