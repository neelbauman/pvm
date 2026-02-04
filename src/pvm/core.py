import json
import shutil
import difflib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import typer
from rich.console import Console

from .config import find_project_root, HIDDEN_DIR

# --- Helper Functions ---

def ensure_global_gitignore(root_path: Path):
    """
    .prompts ディレクトリのルートに .gitignore を作成し、配下の全ファイルをGitから無視させます。
    """
    prompts_dir = root_path / HIDDEN_DIR
    prompts_dir.mkdir(parents=True, exist_ok=True)
    
    gitignore_path = prompts_dir / ".gitignore"
    if not gitignore_path.exists():
        with open(gitignore_path, "w", encoding="utf-8") as f:
            f.write("# Ignore everything in this directory\n*\n")

def get_store_path(target_file: Path) -> Path:
    """
    対象ファイルの履歴を保存するためのディレクトリパス（.prompts内）を生成します。
    """
    target_abs = target_file.resolve()
    root = find_project_root(target_abs)
    
    # プロジェクトルートの .prompts/.gitignore を保証する
    ensure_global_gitignore(root)

    try:
        # プロジェクトルートからの相対パスを取得して構造をミラーリング
        rel_path = target_abs.relative_to(root)
    except ValueError:
        # ルート外ファイルの場合は直下に作成 (Fallback)
        return target_file.parent / HIDDEN_DIR / target_file.name
    return root / HIDDEN_DIR / rel_path

def load_meta(store_path: Path) -> List[Dict]:
    meta_file = store_path / "meta.json"
    if not meta_file.exists():
        return []
    with open(meta_file, "r", encoding="utf-8") as f:
        return json.load(f)

def save_meta(store_path: Path, data: List[Dict]):
    with open(store_path / "meta.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_latest_version(history: List[Dict]) -> str:
    if not history:
        return "0.0.0"
    return history[0]["version"]

def parse_version(ver: str) -> Tuple[int, int, int]:
    try:
        parts = list(map(int, ver.split(".")))
        # 桁数が足りない場合は0で埋める
        if len(parts) < 3:
            parts += [0] * (3 - len(parts))
        return tuple(parts[:3])
    except ValueError:
        return (0, 0, 0)

# --- Business Logic ---

def _start_tracking_internal(file: Path, console: Console):
    """
    内部関数: 指定されたファイル（存在確認済み）の追跡を開始し、初期スナップショットを作成します。
    """
    store_path = get_store_path(file)
    
    if (store_path / "meta.json").exists():
        console.print(f"[yellow]Already tracking {file}.[/yellow]")
        return
    
    store_path.mkdir(parents=True, exist_ok=True)
    
    # 初期コミットの作成
    initial_ver = "0.1.0"
    artifact_name = f"v{initial_ver}_{file.name}"
    shutil.copy(file, store_path / artifact_name)
    
    entry = {
        "version": initial_ver,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "message": "Initial commit",
        "filename": artifact_name
    }
    save_meta(store_path, [entry])
    console.print(f"[green]Started tracking {file} at version {initial_ver}[/green]")
    console.print("[dim]Note: Versions are tracked in .prompts/ (Non-intrusive)[/dim]")

def create_new_file(file: Path, content: str, console: Console):
    """
    initコマンド用: 新規ファイルを作成して追跡を開始します。
    親ディレクトリが存在しない場合は再帰的に作成します。
    """
    if file.exists():
        console.print(f"[red]Error:[/red] File {file} already exists. Use 'pvm track' to track existing files.")
        raise typer.Exit(1)
    
    # 親ディレクトリの自動作成 (mkdir -p)
    if not file.parent.exists():
        file.parent.mkdir(parents=True, exist_ok=True)
        console.print(f"[dim]Created directory: {file.parent}[/dim]")

    console.print(f"[cyan]Creating {file} ...[/cyan]")
    with open(file, "w", encoding="utf-8") as f:
        f.write(content)
        
    _start_tracking_internal(file, console)

def track_existing_file(file: Path, console: Console):
    """
    trackコマンド用: 既存ファイルの追跡を開始します。
    """
    if not file.exists():
        console.print(f"[red]Error:[/red] File {file} does not exist. Use 'pvm init' to create a new file.")
        raise typer.Exit(1)

    _start_tracking_internal(file, console)

def commit_file(
    file: Path, 
    message: str, 
    major: bool, 
    minor: bool, 
    patch: bool, 
    console: Console
):
    """
    commitコマンド用: 変更を検知し、新しいバージョンを保存します。
    """
    store_path = get_store_path(file)
    if not store_path.exists():
        console.print(f"[red]Not initialized. Run 'pvm track {file}' first.[/red]")
        raise typer.Exit(1)

    history = load_meta(store_path)
    latest_ver = parse_version(get_latest_version(history))

    # 変更検知
    if history:
        last_file_path = store_path / history[0]["filename"]
        if last_file_path.exists():
            with open(file, "rb") as f_curr, open(last_file_path, "rb") as f_last:
                if f_curr.read() == f_last.read():
                    console.print("[yellow]Warning: No changes detected since the last snapshot.[/yellow]")
                    if not typer.confirm("Force commit?"):
                        raise typer.Abort()

    # バージョン算出
    cv = latest_ver
    if major:
        nv = [cv[0] + 1, 0, 0]
    elif patch:
        nv = [cv[0], cv[1], cv[2] + 1]
    else: # Default is minor (0.1.0 -> 0.2.0)
        nv = [cv[0], cv[1] + 1, 0]
    new_ver_str = f"{nv[0]}.{nv[1]}.{nv[2]}"

    if message is None:
        message = f"Update version to {new_ver_str}"

    artifact_name = f"v{new_ver_str}_{file.name}"
    shutil.copy(file, store_path / artifact_name)

    new_entry = {
        "version": new_ver_str,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "message": message,
        "filename": artifact_name
    }
    history.insert(0, new_entry)
    save_meta(store_path, history)
    
    console.print(f"[bold green]Committed {new_ver_str}[/bold green]: {message}")

def list_all_tracked_files(root: Path) -> List[Dict]:
    """
    プロジェクト内の全ての追跡ファイルを探索し、状態（存在するかどうか）を含めて返します。
    """
    prompts_root = root / HIDDEN_DIR
    results = []

    if not prompts_root.exists():
        return results

    # .prompts ディレクトリ内を再帰的に探索して meta.json を探す
    for meta_file in prompts_root.rglob("meta.json"):
        store_dir = meta_file.parent
        history = load_meta(store_dir)
        if not history:
            continue

        # ディレクトリ構造から元のファイルパスを逆算
        try:
            rel_path = store_dir.relative_to(prompts_root)
            original_file_path = root / rel_path
        except ValueError:
            original_file_path = root / store_dir.name

        exists = original_file_path.exists()
        
        results.append({
            "path": str(rel_path),
            "latest_version": get_latest_version(history),
            "last_modified": history[0]["timestamp"],
            "exists": exists,
        })
    
    return sorted(results, key=lambda x: x["path"])

def diff_file(file: Path, version: str, console: Console):
    if not file.exists():
        console.print(f"[red]Error:[/red] File {file} does not exist. Use 'checkout' to restore it.")
        raise typer.Exit(1)

    store_path = get_store_path(file)
    history = load_meta(store_path)
    target = next((i for i in history if i["version"] == version), None)
    
    if not target:
        console.print(f"[red]Version {version} not found.[/red]")
        raise typer.Exit(1)
        
    old_path = store_path / target["filename"]
    with open(old_path, "r", encoding="utf-8") as f:
        old_lines = f.readlines()
    with open(file, "r", encoding="utf-8") as f:
        new_lines = f.readlines()
        
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=f"v{version}", tofile="current", lineterm="")
    for line in diff:
        style = "green" if line.startswith("+") else "red" if line.startswith("-") else "cyan" if line.startswith("@") else None
        console.print(line, style=style, end="")

def checkout_file(file: Path, version: str, console: Console):
    """
    指定バージョンを復元します。
    親ディレクトリごと削除されていても復元します。
    """
    store_path = get_store_path(file)
    history = load_meta(store_path)
    target = next((i for i in history if i["version"] == version), None)
    
    if not target:
        console.print(f"[red]Version {version} not found.[/red]")
        raise typer.Exit(1)
        
    src = store_path / target["filename"]
    
    if file.exists():
        msg = f"Overwrite {file} with version {version}?"
    else:
        msg = f"File {file} is missing. Restore version {version}?"

    if not typer.confirm(msg):
        raise typer.Abort()

    # 親ディレクトリがない場合は作成する
    if not file.parent.exists():
        file.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy(src, file)
    console.print(f"[bold yellow]Restored {version} to {file}[/bold yellow]")

