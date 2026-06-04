import time
import shutil

from rich.console import Console, Group
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.spinner import Spinner
from rich import box


BANNER = r"""
╔══════════════════════════════════════════════╗
║        GOST Report Generator                 ║
║    Генерация отчётов о НИР по ГОСТ 7.32      ║
╚══════════════════════════════════════════════╝
"""


class ProgressTracker:
    STAGES = [
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

    def __init__(self):
        self._steps = {}
        for key, label in self.STAGES:
            self._steps[key] = {
                'label': label,
                'status': 'pending',
                'start_time': None,
                'elapsed': None,
                'detail': '',
                'spinner': None,
            }
        self._dashboard = None
        self.project = ''
        self.output = ''
        self.model = ''

    def attach(self, dashboard):
        self._dashboard = dashboard

    def update(self, step, status, detail=None):
        if step not in self._steps:
            return
        s = self._steps[step]
        s['status'] = status
        if detail is not None:
            s['detail'] = str(detail)
        if status == 'running':
            if s['start_time'] is None:
                s['start_time'] = time.time()
            s['spinner'] = Spinner('dots', style='yellow')
        else:
            s['spinner'] = None
        if status in ('completed', 'failed'):
            started = s.get('start_time') or time.time()
            s['elapsed'] = time.time() - started
        if self._dashboard:
            self._dashboard.refresh()

    def mark_build_skipped(self):
        for key, _, s in self._iter():
            if s['status'] == 'pending':
                s['status'] = 'completed'
                s['detail'] = 'пропущен'
                s['elapsed'] = 0
        if self._dashboard:
            self._dashboard.refresh()

    def _iter(self):
        for key, label in self.STAGES:
            yield key, label, self._steps[key]

    def render(self):
        header = Panel(
            Text(BANNER.strip(), style='bold cyan'),
            box=box.HEAVY,
            border_style='cyan',
        )

        info = Table.grid(padding=(0, 1))
        info.add_column(style='bold')
        info.add_column()
        info.add_row('Проект:', self.project)
        info.add_row('Отчёт:',  self.output)
        if self.model:
            info.add_row('Модель:', self.model)
        info_panel = Panel(info, title='Информация', border_style='blue')

        table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        table.add_column(width=2, no_wrap=True)
        table.add_column(no_wrap=True)
        table.add_column(width=10, no_wrap=True)
        table.add_column(no_wrap=True)

        stage_prefix = {'scan': '1/3', 'analyze': '2/3'}
        completed = 0
        total = 0
        now = time.time()
        for key, label, s in self._iter():
            total += 1
            if s['status'] == 'completed':
                completed += 1

            status_style = {
                'completed': 'green',
                'running': 'yellow',
                'failed': 'red',
                'pending': 'bright_black',
            }[s['status']]

            if s['status'] == 'running' and s['spinner']:
                icon = s['spinner']
            else:
                icon_map = {
                    'completed': '●',
                    'running': '◉',
                    'failed': '✖',
                    'pending': '○',
                }
                icon = Text(icon_map[s['status']], style=status_style)

            prefix = ''
            if key in stage_prefix:
                prefix = f'[{stage_prefix[key]}] '

            name = Text(f'{prefix}{label}', style=status_style)

            elapsed = s['elapsed']
            if s['status'] == 'running' and s['start_time']:
                elapsed = now - s['start_time']
            if elapsed is not None:
                if elapsed < 60:
                    time_str = f'{elapsed:.1f}s'
                else:
                    m = int(elapsed // 60)
                    sec = elapsed % 60
                    time_str = f'{m}м {sec:.0f}с'
                time_cell = Text(time_str, style='cyan')
            else:
                time_cell = Text('—', style='bright_black')

            detail = Text(s['detail'], style=status_style)
            table.add_row(icon, name, time_cell, detail)

        progress_header = Text(
            f'Прогресс: {completed}/{total}',
            style='bold green' if completed == total else 'bold',
        )
        progress_panel = Panel(
            table,
            title=progress_header,
            border_style='green' if completed == total else 'yellow',
        )

        return Group(header, info_panel, progress_panel)


class Dashboard:
    def __init__(self, tracker, console=None):
        self.tracker = tracker
        if console:
            self.console = console
        else:
            w = shutil.get_terminal_size().columns
            self.console = Console(width=min(w, 96))
        self._live = None

    def __enter__(self):
        self.tracker.attach(self)
        self._live = Live(
            self.tracker.render(),
            console=self.console,
            refresh_per_second=4,
            vertical_overflow='crop',
            screen=True,
            redirect_stdout=False,
            redirect_stderr=False,
            get_renderable=self.tracker.render,
        )
        self._live.__enter__()
        return self

    def __exit__(self, *args):
        if self._live:
            self._live.__exit__(*args)
            self._live = None

    def refresh(self):
        if self._live:
            self._live.refresh()

    def stop(self):
        if self._live:
            self._live.stop()
            self._live = None

    def final_summary(self, result_path, result_size, elapsed):
        self.stop()
        summary = Panel(
            f'Результат: {result_path} ({result_size})\n'
            f'Время:     {elapsed:.1f} сек',
            border_style='green',
            title='Готово',
        )
        self.console.print()
        self.console.print(summary)
