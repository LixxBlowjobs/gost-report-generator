import os, sys, json, argparse, time
from datetime import datetime

from .analyzer.scanner import scan_project
from .analyzer.llm_analyzer import analyze
from .report import build_report
from .ui import ProgressTracker, Dashboard
from . import llm as llm_mod


def _fmt_size(b: int) -> str:
    if b < 1024:
        return f"{b} B"
    if b < 1024 * 1024:
        return f"{b/1024:.1f} KB"
    return f"{b/1024/1024:.1f} MB"


def _load_env_file(path: str = ".env") -> None:
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
  %(prog)s                                         # TUI-интерфейс
  %(prog)s -p /path/to/project                     # CLI с дашбордом
  %(prog)s -p /path/to/project --simple            # без live-панели
  %(prog)s --check-models                          # проверка моделей
""",
    )
    parser.add_argument("-p", "--project",
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
    parser.add_argument("--simple", action="store_true",
                        help="Простой вывод без live-панели")
    parser.add_argument("--check-models", action="store_true",
                        help="Проверить доступность моделей из LLM_FALLBACK_CHAIN")

    args = parser.parse_args()

    # ── API key ──
    if args.api_key:
        os.environ["OPENROUTER_API_KEY"] = args.api_key
    has_key = bool(os.environ.get("OPENROUTER_API_KEY", ""))

    # ── Check models ──
    if args.check_models:
        _run_check_models(has_key)
        return

    # ── TUI mode (default when no arguments) ──
    if not args.project:
        from .tui_app import run_tui
        run_tui()
        return

    if not os.path.isdir(args.project):
        print(f"  ✗ Путь не найден: {args.project}")
        sys.exit(1)

    if not has_key and not args.skip_llm:
        print("  ! OPENROUTER_API_KEY не задан — переход в --skip-llm")
        args.skip_llm = True

    if not args.save_analysis:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.save_analysis = f"analysis_{ts}.json"

    # ── Simple mode: old behaviour ──
    if args.simple:
        _run_simple(args)
        return

    # ── Dashboard mode ──
    tracker = ProgressTracker()
    tracker.project = args.project
    tracker.output = args.output
    tracker.model = 'LLM' if not args.skip_llm else 'только сканирование'

    dashboard = Dashboard(tracker)

    llm_mod.SUPPRESS_STDERR = True

    with dashboard:
        t_start = time.time()

        try:
            # ── Stage 1: scan ──
            tracker.update('scan', 'running')
            scan = scan_project(args.project)
            tracker.update('scan', 'completed',
                           detail=f"{scan.get('total_files', 0)} файлов, {scan.get('total_size_kb', 0)} KB")

            # ── Stage 2: LLM analysis or cached ──
            analysis = None
            if args.analysis:
                tracker.update('analyze', 'running',
                               detail=f'загрузка из {args.analysis}')
                with open(args.analysis, encoding="utf-8") as f:
                    analysis = json.load(f)
                pn = analysis.get('project_name', '?')
                tracker.update('analyze', 'completed', detail=pn)
            elif not args.skip_llm:
                tracker.update('analyze', 'running',
                               detail='gemini-2.0-flash...')
                try:
                    analysis = analyze(scan)
                    pn = analysis.get('project_name', '?')
                    tracker.update('analyze', 'completed', detail=pn)
                except Exception as e:
                    tracker.update('analyze', 'failed', detail=str(e))
                    args.skip_llm = True

            if args.analyze_only:
                if analysis:
                    with open(args.save_analysis, "w", encoding="utf-8") as f:
                        json.dump(analysis, f, indent=2, ensure_ascii=False)
                    tracker.mark_build_skipped()
                    dashboard.final_summary(
                        args.save_analysis,
                        _fmt_size(os.path.getsize(args.save_analysis)),
                        time.time() - t_start,
                    )
                return

            # ── Stage 3: build report ──
            metadata = {}
            if args.metadata:
                try:
                    with open(args.metadata, encoding="utf-8") as f:
                        metadata = json.load(f)
                except Exception:
                    pass

            build_report(
                analysis or scan,
                metadata,
                args.output,
                analysis_path=args.save_analysis if analysis else None,
                skip_postprocess=args.no_postprocess,
                progress=tracker,
            )

            elapsed = time.time() - t_start
            if os.path.exists(args.output):
                dashboard.final_summary(
                    args.output,
                    _fmt_size(os.path.getsize(args.output)),
                    elapsed,
                )

        except Exception as e:
            dashboard.stop()
            print(f"  ✗ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


def _run_simple(args):
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from .ui import BANNER

    console = Console(width=88)

    console.print(Panel(Text(BANNER.strip(), style='bold cyan'),
                        border_style='cyan'))
    console.print()

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

    # ── Stage 2: analysis ──
    analysis = None
    if args.analysis:
        print(f"  [2/3] Загрузка анализа из {args.analysis}...", end=" ", flush=True)
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
            progress=None,
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


def _run_check_models(has_key: bool):
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.style import Style
    from httpx import Client, Timeout

    from .config import LLM_FALLBACK_CHAIN, OPENROUTER_BASE_URL

    console = Console()

    if not has_key:
        console.print(Panel(
            "OPENROUTER_API_KEY не задан.\n"
            "Укажите ключ в .env или через --api-key.",
            border_style='red', title='Ошибка',
        ))
        sys.exit(1)

    console.print(Panel(
        Text("Проверка моделей OpenRouter", style='bold cyan'),
        border_style='cyan',
    ))
    console.print()

    table = Table(box=None, padding=(0, 2))
    table.add_column('', width=2)
    table.add_column('Модель')
    table.add_column('Статус', width=10)
    table.add_column('Детали')

    headers = {
        "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
    }
    ok = 0

    with Client(timeout=Timeout(15.0)) as client:
        # Get available models list
        try:
            resp = client.get(f"{OPENROUTER_BASE_URL}/models", headers=headers)
            resp.raise_for_status()
            available = {m['id'] for m in resp.json().get('data', [])}
        except Exception:
            available = set()

        for model in LLM_FALLBACK_CHAIN:
            table.add_row('', Text(f'  {model}', style='bold'), '', '')

            # Check 1: model exists in catalog
            if model in available:
                table.add_row(
                    Text('●', style='green'),
                    '', Text('доступна', style='green'),
                    Text('в каталоге', style='green'),
                )
            else:
                table.add_row(
                    Text('○', style='bright_black'),
                    '', Text('не найдена', style='bright_black'),
                    Text('отсутствует в каталоге OpenRouter', style='bright_black'),
                )

            # Check 2: try a minimal API call
            try:
                r = client.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    headers=headers,
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": "test"}],
                        "max_tokens": 1,
                    },
                )
                if r.status_code == 200:
                    table.add_row(
                        Text('●', style='green'),
                        '', Text('работает', style='green'),
                        Text('ответ 200 OK', style='green'),
                    )
                    ok += 1
                elif r.status_code == 401:
                    table.add_row(
                        Text('✖', style='red'),
                        '', Text('ошибка', style='red'),
                        Text('401 — неверный API ключ', style='red'),
                    )
                else:
                    detail = r.json().get('error', {}).get('message', str(r.status_code))
                    table.add_row(
                        Text('✖', style='red'),
                        '', Text('ошибка', style='red'),
                        Text(detail, style='red'),
                    )
            except Exception as e:
                table.add_row(
                    Text('✖', style='red'),
                    '', Text('ошибка', style='red'),
                    Text(str(e)[:60], style='red'),
                )

            table.add_row('', '', '', '')

    console.print(table)
    console.print()
    console.print(Panel(
        f"Работает: {ok}/{len(LLM_FALLBACK_CHAIN)}  |  "
        f"Цепочка: {LLM_FALLBACK_CHAIN}",
        border_style='green' if ok else 'yellow',
    ))


if __name__ == "__main__":
    main()
