import os, json
from pathlib import Path


def _is_binary(path: Path) -> bool:
    BINARY_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".pdf",
                   ".docx", ".xlsx", ".pptx", ".zip", ".tar", ".gz", ".bz2",
                   ".pyc", ".pyo", ".so", ".dll", ".dylib", ".o", ".a",
                   ".woff", ".woff2", ".ttf", ".eot",
                   ".mp3", ".mp4", ".avi", ".mov", ".wav",
                   ".svg", ".webp"}
    return path.suffix.lower() in BINARY_EXTS


IGNORE_DIRS = {".git", ".venv", ".idea", "__pycache__", "node_modules",
               "target", "build", "dist", ".hg", ".svn", ".terraform",
               ".next", ".nuxt", "vendor", "Pods", ".tox", ".mypy_cache",
               ".pytest_cache", ".ruff_cache", ".eggs", "*.egg-info"}

CONFIG_FILES = {
    "package.json", "pyproject.toml", "Cargo.toml", "build.gradle",
    "build.gradle.kts", "CMakeLists.txt", "composer.json", "go.mod",
    "Cargo.lock", "Gemfile", "Podfile", "requirements.txt",
    "Dockerfile", "docker-compose.yml", "Makefile",
    ".env.example", ".gitignore", "README.md", "README",
}

MAX_FILE_SIZE = 50 * 1024  # 50 KB


def scan_project(project_dir: str) -> dict:
    root = Path(project_dir).resolve()
    tree = []
    files_by_ext = {}
    configs = {}
    source_files = []
    total_size = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        rel_dir = Path(dirpath).relative_to(root)
        if rel_dir.as_posix() == ".":
            rel_dir_str = ""
        else:
            rel_dir_str = rel_dir.as_posix()

        level = len(rel_dir.parts) if rel_dir_str else 0
        indent = "  " * level
        if rel_dir_str:
            tree.append(f"{indent}{rel_dir.name}/")

        for fname in sorted(filenames):
            fpath = Path(dirpath) / fname
            if _is_binary(fpath):
                continue
            ext = fpath.suffix.lower() or "(no ext)"
            files_by_ext[ext] = files_by_ext.get(ext, 0) + 1
            fsize = fpath.stat().st_size
            total_size += fsize

            tree.append(f"{indent}  {fname}")

            if fname in CONFIG_FILES:
                try:
                    content = fpath.read_text("utf-8", errors="replace")[:2000]
                    configs[fname] = content
                except Exception:
                    pass

            if ext in (".py", ".js", ".ts", ".kt", ".java", ".go", ".rs",
                       ".c", ".cpp", ".h", ".hpp", ".swift", ".rb", ".php",
                       ".sh", ".bash", ".zsh", ".yml", ".yaml", ".json",
                       ".xml", ".toml", ".cfg", ".ini", ".conf",
                       ".css", ".scss", ".html", ".vue", ".svelte",
                       ".sql", ".r", ".m", ".mm"):
                if fsize <= MAX_FILE_SIZE and fsize > 0:
                    source_files.append({
                        "path": str(fpath.relative_to(root)),
                        "size": fsize,
                        "ext": ext,
                    })

    source_files.sort(key=lambda x: -x["size"])
    top_sources = source_files[:30]

    top_contents = {}
    for sf in top_sources:
        try:
            fpath = root / sf["path"]
            content = fpath.read_text("utf-8", errors="replace")
            top_contents[sf["path"]] = content
        except Exception:
            pass

    result = {
        "project_dir": project_dir,
        "project_name": root.name,
        "total_files": sum(files_by_ext.values()),
        "total_size_kb": round(total_size / 1024, 1),
        "files_by_ext": dict(sorted(files_by_ext.items(),
                                     key=lambda x: -x[1])),
        "tree": "\n".join(tree),
        "configs": configs,
        "top_source_files": top_contents,
    }
    return result
