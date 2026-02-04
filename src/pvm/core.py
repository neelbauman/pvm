import json
import shutil
import difflib
import hashlib
import os
import stat
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any

import typer
from rich.console import Console

from .config import find_project_root, HIDDEN_DIR

LOCK_FILE_NAME = ".pvm-lock.json"

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
    
    ensure_global_gitignore(root)

    try:
        rel_path = target_abs.relative_to(root)
    except ValueError:
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
        if len(parts) < 3:
            parts += [0] * (3 - len(parts))
        return tuple(parts[:3])
    except ValueError:
        return (0, 0, 0)

def calculate_file_hash(file_path: Path) -> str:
    """ファイルのSHA256ハッシュを計算します。"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # メモリ効率のためチャンク読み込み
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def identify_version_by_content(file_path: Path, store_path: Path) -> Optional[str]:
    """
    現在のファイル内容と一致するバージョンを履歴から検索します。
    一致するものがない場合は None を返します（Dirty状態）。
    """
    if not file_path.exists():
        return None
        
    current_hash = calculate_file_hash(file_path)
    history = load_meta(store_path)
    
    for entry in history:
        snapshot_path = store_path / entry["filename"]
        if snapshot_path.exists():
            if calculate_file_hash(snapshot_path) == current_hash:
                return entry["version"]
    return None

# --- Business Logic ---

def _start_tracking_internal(file: Path, console: Console):
    store_path = get_store_path(file)
    
    if (store_path / "meta.json").exists():
        console.print(f"[yellow]Already tracking {file}.[/yellow]")
        return
    
    store_path.mkdir(parents=True, exist_ok=True)
    
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
    if file.exists():
        console.print(f"[red]Error:[/red] File {file} already exists. Use 'pvm track' to track existing files.")
        raise typer.Exit(1)
    
    if not file.parent.exists():
        file.parent.mkdir(parents=True, exist_ok=True)
        console.print(f"[dim]Created directory: {file.parent}[/dim]")

    console.print(f"[cyan]Creating {file} ...[/cyan]")
    with open(file, "w", encoding="utf-8") as f:
        f.write(content)
        
    _start_tracking_internal(file, console)

def track_existing_file(file: Path, console: Console):
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
    store_path = get_store_path(file)
    if not store_path.exists():
        console.print(f"[red]Not initialized. Run 'pvm track {file}' first.[/red]")
        raise typer.Exit(1)

    history = load_meta(store_path)
    latest_ver = parse_version(get_latest_version(history))

    if history:
        last_file_path = store_path / history[0]["filename"]
        if last_file_path.exists():
            # 内容比較 (ハッシュは使わずバイナリ比較で十分高速)
            with open(file, "rb") as f_curr, open(last_file_path, "rb") as f_last:
                if f_curr.read() == f_last.read():
                    console.print("[yellow]Warning: No changes detected since the last snapshot.[/yellow]")
                    if not typer.confirm("Force commit?"):
                        raise typer.Abort()

    cv = latest_ver
    # Priority: Major > Patch > Minor (Default)
    if major:
        nv = [cv[0] + 1, 0, 0]
    elif patch:
        nv = [cv[0], cv[1], cv[2] + 1]
    else: 
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
    prompts_root = root / HIDDEN_DIR
    results = []

    if not prompts_root.exists():
        return results

    for meta_file in prompts_root.rglob("meta.json"):
        store_dir = meta_file.parent
        history = load_meta(store_dir)
        if not history:
            continue

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

def checkout_file(file: Path, version: str, console: Console, confirm: bool = True):
    """
    指定バージョンを復元します。
    confirm=False の場合はユーザー確認をスキップします（Sync用）。
    """
    store_path = get_store_path(file)
    history = load_meta(store_path)
    target = next((i for i in history if i["version"] == version), None)
    
    if not target:
        console.print(f"[red]Version {version} not found for {file}[/red]")
        # Sync時にエラーを返したい場合は Exception を投げるか検討
        return False
        
    src = store_path / target["filename"]
    
    if confirm:
        if file.exists():
            msg = f"Overwrite {file} with version {version}?"
        else:
            msg = f"File {file} is missing. Restore version {version}?"

        if not typer.confirm(msg):
            raise typer.Abort()

    if not file.parent.exists():
        file.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy(src, file)
    console.print(f"[bold yellow]Restored {version} to {file}[/bold yellow]")
    return True

# --- Lock File & Reproducibility Logic (v1.0.0) ---

def create_lock_file(console: Console):
    """
    現在のワークツリーの状態をスキャンし、.pvm-lock.json を生成します。
    各ファイルのハッシュを計算し、PVM履歴と照合してバージョンを特定します。
    """
    root = find_project_root(Path.cwd())
    tracked_files = list_all_tracked_files(root)
    
    lock_data = {
        "version": 1,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "files": {}
    }
    
    console.print("[cyan]Generating lock file...[/cyan]")
    
    for item in tracked_files:
        rel_path_str = item["path"]
        full_path = root / rel_path_str
        store_path = root / HIDDEN_DIR / rel_path_str
        
        if not full_path.exists():
            # ファイルが存在しない場合はロックファイルに含めない、あるいは "missing" として記録するか？
            # ここでは「存在するものだけをロックする」方針とする
            continue
            
        # 現在のファイル内容からバージョンを逆引き
        matched_version = identify_version_by_content(full_path, store_path)
        
        status_msg = ""
        if matched_version:
            status_msg = f"[green]{matched_version}[/green]"
            lock_data["files"][rel_path_str] = {
                "version": matched_version,
                "hash": calculate_file_hash(full_path)
            }
        else:
            status_msg = "[yellow]Dirty (Uncommitted)[/yellow]"
            # Dirtyな場合でも、現状のハッシュは記録しておく（Sync時の比較用）
            lock_data["files"][rel_path_str] = {
                "version": None,
                "hash": calculate_file_hash(full_path)
            }
            
        console.print(f"  {rel_path_str}: {status_msg}")

    lock_file_path = root / LOCK_FILE_NAME
    with open(lock_file_path, "w", encoding="utf-8") as f:
        json.dump(lock_data, f, indent=2, ensure_ascii=False)
        
    console.print(f"[bold green]Lock file updated: {LOCK_FILE_NAME}[/bold green]")
    console.print("[dim]Don't forget to 'git add .pvm-lock.json'[/dim]")

def sync_from_lock_file(console: Console):
    """
    .pvm-lock.json に記載されたバージョンに従って、ファイルを復元（チェックアウト）します。
    """
    root = find_project_root(Path.cwd())
    lock_file_path = root / LOCK_FILE_NAME
    
    if not lock_file_path.exists():
        console.print(f"[red]Lock file {LOCK_FILE_NAME} not found.[/red]")
        raise typer.Exit(1)
        
    with open(lock_file_path, "r", encoding="utf-8") as f:
        lock_data = json.load(f)
        
    files_map = lock_data.get("files", {})
    if not files_map:
        console.print("[yellow]Lock file is empty.[/yellow]")
        return

    console.print(f"[cyan]Syncing {len(files_map)} files from lock...[/cyan]")
    
    restored_count = 0
    skipped_count = 0
    
    for rel_path_str, info in files_map.items():
        target_version = info.get("version")
        full_path = root / rel_path_str
        
        if target_version is None:
            console.print(f"  [yellow]Skip {rel_path_str}: Recorded as Dirty[/yellow]")
            skipped_count += 1
            continue
            
        # 現在の状態を確認（既に同じバージョンならスキップ）
        current_ver = None
        if full_path.exists():
            store_path = root / HIDDEN_DIR / rel_path_str
            current_ver = identify_version_by_content(full_path, store_path)
            
        if current_ver == target_version:
            # console.print(f"  [dim]Skip {rel_path_str}: Already matches {target_version}[/dim]")
            continue
            
        # 復元実行 (確認なし)
        success = checkout_file(full_path, target_version, console, confirm=False)
        if success:
            restored_count += 1
        else:
            console.print(f"  [red]Failed to sync {rel_path_str} (Version {target_version} not found in history)[/red]")

    console.print(f"[green]Sync complete.[/green] Restored: {restored_count}, Skipped: {skipped_count}")

def install_hooks(console: Console):
    """
    Gitの pre-commit フックをインストールし、コミット時に自動でロックファイルを更新するようにします。
    """
    root = find_project_root(Path.cwd())
    git_dir = root / ".git"
    
    if not git_dir.exists():
        console.print("[red]Not a git repository.[/red] Run 'git init' first.")
        raise typer.Exit(1)
        
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    
    pre_commit_path = hooks_dir / "pre-commit"
    
    # シンプルなシェルスクリプト
    script_content = f"""#!/bin/sh
# Installed by PVM v1.0.0

echo "[PVM] Updating {LOCK_FILE_NAME}..."
pvm lock

if [ $? -ne 0 ]; then
    echo "[PVM] Error: Failed to update lock file."
    exit 1
fi

git add {LOCK_FILE_NAME}
echo "[PVM] Lock file updated and staged."
"""
    
    if pre_commit_path.exists():
        console.print(f"[yellow]Warning: {pre_commit_path} already exists.[/yellow]")
        if not typer.confirm("Overwrite existing hook?"):
            raise typer.Abort()
            
    with open(pre_commit_path, "w", encoding="utf-8") as f:
        f.write(script_content)
        
    # 実行権限を付与 (chmod +x)
    st = os.stat(pre_commit_path)
    os.chmod(pre_commit_path, st.st_mode | stat.S_IEXEC)
    
    console.print(f"[green]Hook installed to {pre_commit_path}[/green]")
    console.print("`pvm lock` will now run automatically on `git commit`.")

