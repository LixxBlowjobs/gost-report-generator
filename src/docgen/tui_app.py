import os, sys, json, time, asyncio, re
from pathlib import Path
from typing import Optional
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header, Footer, Input, Button, Static, Checkbox, Label, RichLog,
    TextArea, ListView, ListItem,
)
from textual.screen import Screen, ModalScreen
from textual.binding import Binding
from textual import work
from textual.reactive import reactive

from .config import LLM_FALLBACK_CHAIN
from . import llm as llm_mod


# ── Helpers ──

def _load_env():
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ── Adapter: TUI step tracker → report.py progress callback ──

class TuiProgressAdapter:
    def __init__(self, screen: "ProgressScreen"):
        self.screen = screen

    def update(self, step: str, status: str, detail: str = ""):
        self.screen.update_step(step, status, detail or "")

    def log(self, msg: str):
        self.screen.log_write(msg + "\n")


# ── Progress Screen ──

class ProgressScreen(Screen):
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.steps = [
            ('scan',          'Сканирование'),
            ('analyze',       'Анализ проекта'),
            ('plan',          'План отчёта'),
            ('references',    'Литература'),
            ('introduction',  'Введение'),
            ('chapter_1',     'Глава 1'),
            ('chapter_2',     'Глава 2'),
            ('chapter_3',     'Глава 3'),
            ('conclusion',    'Заключение'),
            ('terms',         'Термины'),
            ('abstract',      'Реферат'),
            ('postprocess',   'Постобработка'),
            ('build_docx',    'Сборка DOCX'),
        ]
        self._state = {k: 'pending' for k, _ in self.steps}
        self._labels = dict(self.steps)
        self._start_times = {}
        self._detail = {}
        self._log_buffer: list[str] = []
        self._result = None
        self._error = None

    def compose(self):
        yield Header(show_clock=True)
        with Vertical(id="progress-container"):
            yield Label("Генерация отчёта", id="progress-title")
            yield Static("", id="progress-stats")
            with Horizontal(id="progress-body"):
                with ScrollableContainer(id="progress-steps"):
                    for key, label in self.steps:
                        yield Static(f"  ○  {label}", id=f"step-{key}", classes="step-row step-pending")
                yield RichLog(id="progress-log", highlight=True, markup=True, wrap=True)
        yield Footer()

    def on_mount(self):
        self.run_generation()
        self.set_interval(1.0, self._refresh_timers)

    def log_write(self, msg: str):
        self._log_buffer.append(msg)

    def _step_text(self, key: str) -> str:
        icons = {'completed': '●', 'running': '◉', 'failed': '✖', 'pending': '○'}
        icon = icons.get(self._state.get(key, 'pending'), '○')
        label = self._labels.get(key, key)
        elapsed = ""
        if key in self._start_times:
            e = time.time() - self._start_times[key]
            elapsed = f" ({e:.1f}s)"
        detail = self._detail.get(key, "")
        detail_text = f"  —  {detail}" if detail else ""
        return f"  {icon}  {label}{elapsed}{detail_text}"

    def _flush_log(self):
        buf = self._log_buffer
        if not buf:
            return
        self._log_buffer = []
        log_widget = self.query_one("#progress-log", RichLog)
        for line in buf:
            log_widget.write(line.rstrip())

    def _refresh_timers(self):
        for key in self._start_times:
            if self._state.get(key) == 'running':
                widget = self.query_one(f"#step-{key}", Static)
                widget.update(self._step_text(key))
        self._flush_log()

    def update_step(self, key: str, status: str, detail: str = ""):
        self._state[key] = status
        self._detail[key] = detail
        if status == 'running' and key not in self._start_times:
            self._start_times[key] = time.time()
        widget = self.query_one(f"#step-{key}", Static)
        widget.update(self._step_text(key))
        widget.classes = f"step-row step-{status}"

    def mark_done(self, elapsed: float, output_path: str):
        self._result = (elapsed, output_path)
        stats = self.query_one("#progress-stats", Static)
        if output_path and os.path.exists(output_path):
            size_str = _fmt_size(os.path.getsize(output_path))
            msg = f"[bold green]Готово![/]  {output_path} ({size_str})  —  {elapsed:.1f} сек"
        elif output_path:
            msg = f"[bold green]Готово![/]  {output_path}  —  {elapsed:.1f} сек"
        else:
            msg = f"[bold green]Анализ завершён![/]  —  {elapsed:.1f} сек"
        msg += "\n[dim]Нажмите любую клавишу для возврата[/]"
        stats.update(msg)
        self.query_one("#progress-title", Label).update("✅  Генерация завершена")

    def mark_error(self, msg: str):
        self._error = msg
        stats = self.query_one("#progress-stats", Static)
        ts = datetime.now().strftime("%H:%M:%S")
        stats.update(f"[bold red]Ошибка ({ts}): {msg}[/]\n[dim]Нажмите любую клавишу[/]")
        self.query_one("#progress-title", Label).update("❌  Ошибка генерации")

    def on_key(self, event):
        if self._result is not None or self._error is not None:
            self.dismiss(self._result)

    @work(thread=True)
    def run_generation(self):
        try:
            cfg = self.config
            t_start = time.time()

            # API key
            api_key = cfg.get("api_key") or os.environ.get("OPENROUTER_API_KEY", "")
            if api_key:
                os.environ["OPENROUTER_API_KEY"] = api_key

            skip_llm = cfg.get("skip_llm", False)
            if not api_key and not skip_llm:
                skip_llm = True

            # Stage 1: scan
            self.update_step('scan', 'running')
            from .analyzer.scanner import scan_project
            scan = scan_project(cfg["project"])
            self.update_step('scan', 'completed',
                             f"{scan.get('total_files', 0)} файлов")

            # Stage 2: analysis
            analysis = None
            if not skip_llm:
                self.update_step('analyze', 'running')
                from .analyzer.llm_analyzer import analyze
                try:
                    llm_mod.SUPPRESS_STDERR = True
                    analysis = analyze(scan)
                    pn = analysis.get('project_name', '?')
                    self.update_step('analyze', 'completed', pn)
                except Exception as e:
                    self.update_step('analyze', 'failed', str(e))

            if cfg.get("analyze_only"):
                elapsed = time.time() - t_start
                self.mark_done(elapsed, "")
                return

            # Stage 3: build report
            from .report import build_report
            metadata = {}
            meta_path = cfg.get("metadata")
            if meta_path and os.path.isfile(meta_path):
                with open(meta_path, encoding="utf-8") as f:
                    metadata = json.load(f)

            adapter = TuiProgressAdapter(self)
            build_report(
                analysis or scan,
                metadata,
                cfg.get("output", "report.docx"),
                skip_postprocess=cfg.get("no_postprocess", False),
                progress=adapter,
                log_callback=adapter.log,
            )

            elapsed = time.time() - t_start
            output_path = cfg.get("output", "report.docx")
            self.mark_done(elapsed, output_path)

        except Exception as e:
            self.mark_error(str(e))


# ── Model Check Screen ──

class ModelCheckScreen(Screen):
    BINDINGS = [
        Binding("escape", "dismiss", "Назад"),
    ]

    def __init__(self):
        super().__init__()
        self.results: list[dict] = []

    def compose(self):
        yield Header(show_clock=True)
        with Vertical(id="check-container"):
            yield Label("Проверка моделей OpenRouter", id="check-title")
            with ScrollableContainer(id="check-results"):
                yield Static("Загрузка...", id="check-status")
        yield Footer()

    @work
    async def run_check(self):
        import httpx
        from .config import OPENROUTER_BASE_URL
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            self.query_one("#check-status", Static).update(
                "[red]OPENROUTER_API_KEY не задан[/]"
            )
            return

        container = self.query_one("#check-results", ScrollableContainer)
        await container.remove_children()

        headers = {"Authorization": f"Bearer {api_key}"}
        ok = 0

        async with httpx.AsyncClient(timeout=15.0) as client:
            available = set()
            try:
                resp = await client.get(f"{OPENROUTER_BASE_URL}/models", headers=headers)
                resp.raise_for_status()
                available = {m['id'] for m in resp.json().get('data', [])}
            except Exception:
                pass

            for model in LLM_FALLBACK_CHAIN:
                safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', model)
                row = Static("", id=f"check-{safe_id}")
                await container.mount(row)

                lines = [f"\n  [bold]{model}[/]"]

                if model in available:
                    lines.append(f"  [green]●[/]  доступна   в каталоге")
                else:
                    lines.append(f"  [bright_black]○[/]  отсутствует в каталоге")

                try:
                    r = await client.post(
                        f"{OPENROUTER_BASE_URL}/chat/completions",
                        headers=headers,
                        json={
                            "model": model,
                            "messages": [{"role": "user", "content": "test"}],
                            "max_tokens": 1,
                        },
                    )
                    if r.status_code == 200:
                        lines.append(f"  [green]●[/]  работает    200 OK")
                        ok += 1
                    else:
                        err = r.json().get('error', {}).get('message', str(r.status_code))
                        lines.append(f"  [red]✖[/]  {err}")
                except Exception as e:
                    lines.append(f"  [red]✖[/]  {str(e)[:60]}")

                row.update("\n".join(lines))

        summary = Static(
            f"\n[{'green' if ok else 'yellow'}]Работает: {ok}/{len(LLM_FALLBACK_CHAIN)}[/]"
        )
        await container.mount(summary)

    def on_mount(self):
        self.run_check()


# ── Main Screen ──

class MainScreen(Screen):
    BINDINGS = [
        Binding("ctrl+g", "generate", "Генерировать"),
        Binding("ctrl+m", "check_models", "Проверить модели"),
        Binding("ctrl+q", "quit", "Выход"),
    ]

    def compose(self):
        yield Header(show_clock=True)
        with Vertical(id="main-layout"):
            with Horizontal(classes="config-row"):
                yield Input(
                    placeholder="Путь к проекту",
                    id="input-project", classes="config-input"
                )
                yield Input(
                    placeholder="Файл отчёта (report.docx)",
                    id="input-output", value="report.docx", classes="config-input"
                )
            with Horizontal(classes="flags-row"):
                yield Checkbox("Skip LLM", id="flag-skip-llm")
                yield Checkbox("Analyze Only", id="flag-analyze-only")
                yield Checkbox("No Postprocess", id="flag-no-postprocess")
            yield Button("▶  Сгенерировать отчёт", id="btn-generate", variant="primary")
            yield RichLog(id="log", highlight=True, markup=True, wrap=True)
            yield Input(placeholder="> Введите /help для списка команд...",
                        id="command-input", classes="command-bar")
        yield Footer()

    def on_mount(self):
        log = self.query_one("#log", RichLog)
        log.write("[bold]GOST Report Generator[/]")
        log.write("[dim]Укажите путь к проекту и нажмите «Сгенерировать отчёт»[/]")
        log.write("[dim]Или введите /help для списка команд[/]")
        log.write("")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn-generate":
            self.action_generate()

    def action_generate(self):
        config = self._collect_config()
        if not config.get("project"):
            self._log("[red]Укажите путь к проекту[/]")
            return
        if not os.path.isdir(config["project"]):
            self._log(f"[red]Путь не найден: {config['project']}[/]")
            return

        # Check for metadata.json alongside project
        meta_path = os.path.join(config["project"], "metadata.json")
        if os.path.isfile(meta_path):
            config["metadata"] = meta_path

        self._log(f"[yellow]Запуск генерации для {config['project']}...[/]")
        self.app.push_screen(ProgressScreen(config), self._on_progress_done)

    def _on_progress_done(self, result):
        if result:
            elapsed, output_path = result
            if output_path and os.path.exists(output_path):
                self._log(f"[green]Готово: {output_path} ({_fmt_size(os.path.getsize(output_path))}) — {elapsed:.1f} сек[/]")
            elif output_path:
                self._log(f"[green]Готово: {output_path} — {elapsed:.1f} сек[/]")
            else:
                self._log(f"[green]Анализ завершён — {elapsed:.1f} сек[/]")
        else:
            self._log("[red]Генерация прервана[/]")

    def action_check_models(self):
        self.app.push_screen(ModelCheckScreen())

    def _collect_config(self) -> dict:
        return {
            "project": self.query_one("#input-project", Input).value.strip(),
            "output": self.query_one("#input-output", Input).value.strip() or "report.docx",
            "skip_llm": self.query_one("#flag-skip-llm", Checkbox).value,
            "analyze_only": self.query_one("#flag-analyze-only", Checkbox).value,
            "no_postprocess": self.query_one("#flag-no-postprocess", Checkbox).value,
        }

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.query_one("#log", RichLog).write(f"[dim]{ts}[/] {msg}")

    def handle_command(self, cmd: str):
        parts = cmd.strip().split(maxsplit=1)
        command = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if command in ("/project", "/p"):
            self.query_one("#input-project", Input).value = arg
            self._log(f"Проект: {arg}")
        elif command in ("/output", "/o"):
            self.query_one("#input-output", Input).value = arg or "report.docx"
            self._log(f"Отчёт: {arg or 'report.docx'}")
        elif command in ("/skip-llm", "/skip"):
            cb = self.query_one("#flag-skip-llm", Checkbox)
            cb.value = not cb.value
            self._log(f"Skip LLM: {'вкл' if cb.value else 'выкл'}")
        elif command in ("/analyze-only", "/analyze"):
            cb = self.query_one("#flag-analyze-only", Checkbox)
            cb.value = not cb.value
            self._log(f"Analyze Only: {'вкл' if cb.value else 'выкл'}")
        elif command in ("/no-postprocess", "/no-pp"):
            cb = self.query_one("#flag-no-postprocess", Checkbox)
            cb.value = not cb.value
            self._log(f"No Postprocess: {'вкл' if cb.value else 'выкл'}")
        elif command in ("/generate", "/g"):
            self.action_generate()
        elif command in ("/check-models", "/models", "/check", "/cm"):
            self.action_check_models()
        elif command == "/clear":
            self.query_one("#log", RichLog).clear()
        elif command in ("/help", "/?"):
            self._show_help()
        elif command in ("/quit", "/q", "/exit"):
            self.app.exit()
        else:
            self._log(f"[red]Неизвестная команда: {command}. /help — список команд[/]")

    def _show_help(self):
        help_text = """[bold]Команды:[/]
  [green]/project[/] <path>      — путь к проекту
  [green]/output[/] <path>      — файл отчёта
  [green]/skip-llm[/]           — пропустить LLM (toggle)
  [green]/analyze-only[/]       — только анализ (toggle)
  [green]/no-postprocess[/]     — без постобработки (toggle)
  [green]/generate[/]           — запустить генерацию
  [green]/check-models[/]       — проверить модели
  [green]/clear[/]              — очистить лог
  [green]/help[/]               — это сообщение
  [green]/quit[/]               — выход

[bold]Горячие клавиши:[/]
  [yellow]Ctrl+G[/]  — генерация    [yellow]Ctrl+M[/]  — проверка моделей
  [yellow]Ctrl+Q[/]  — выход
"""
        self._log(help_text)


# ── App ──

class GostReportApp(App):
    TITLE = "GOST Report Generator"
    SUB_TITLE = "Генерация отчётов о НИР по ГОСТ 7.32-2017"
    SCREENS = {"main": MainScreen}
    CSS = """
    Screen {
        background: $surface;
    }

    #main-layout {
        height: 1fr;
        padding: 0 1;
    }

    .config-row {
        height: 3;
        margin: 0 0 0 0;
    }

    .config-input {
        width: 1fr;
        margin: 0 1 0 0;
    }

    .flags-row {
        height: 3;
        margin: 0 0 0 0;
    }

    .flags-row Checkbox {
        margin: 0 2 0 0;
    }

    #btn-generate {
        background: $success;
        color: $text;
        width: 100%;
        margin: 0 0 1 0;
    }

    .command-bar {
        dock: bottom;
        height: 3;
        margin: 0 0 1 0;
        border: none;
    }

    .command-bar:focus {
        border: none;
    }

    /* Progress Screen */
    #progress-container {
        height: 1fr;
        padding: 1 2;
    }

    #progress-title {
        text-style: bold;
        content-align: center top;
        height: 3;
    }

    #progress-stats {
        height: 3;
        margin: 0 0 1 0;
    }

    #progress-body {
        height: 1fr;
    }

    #progress-steps {
        width: 36%;
        border: solid $border;
        padding: 0 1;
        margin: 0 1 0 0;
    }

    #progress-log {
        width: 1fr;
        border: solid $border;
    }

    .step-row {
        margin: 0 0 0 0;
        height: 1;
    }

    .step-pending {
        color: $foreground 50%;
    }

    .step-running {
        color: yellow;
    }

    .step-completed {
        color: green;
    }

    .step-failed {
        color: red;
    }

    /* Model Check Screen */
    #check-container {
        height: 1fr;
        padding: 1 2;
    }

    #check-title {
        text-style: bold;
        content-align: center top;
        height: 3;
    }

    #check-results {
        height: 1fr;
        border: solid $border;
        padding: 0 1;
    }
    """

    def on_mount(self):
        _load_env()
        self.push_screen("main")

    def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == "command-input" and isinstance(self.screen, MainScreen):
            self.screen.handle_command(event.value)
            event.input.value = ""
            event.input.focus()

    def action_quit(self):
        self.exit()


# ── Standalone Runner ──

def run_tui():
    import sys
    try:
        app = GostReportApp()
        app.run()
    except Exception as e:
        with open("/tmp/docgen_tui_error.log", "w") as f:
            import traceback
            traceback.print_exc(file=f)
        print(f"  ✗ TUI error: {e}", file=sys.stderr)
        print("  Лог ошибки: /tmp/docgen_tui_error.log", file=sys.stderr)
        sys.exit(1)


# ── File size helper ──

def _fmt_size(b: int) -> str:
    if b < 1024:
        return f"{b} B"
    if b < 1024 * 1024:
        return f"{b/1024:.1f} KB"
    return f"{b/1024/1024:.1f} MB"
