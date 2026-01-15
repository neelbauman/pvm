import json
import shutil
import difflib
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple

import typer
from rich.console import Console
from rich.table import Table

# アプリケーションの定義
app = typer.Typer(help="Simple Prompt Version Manager for .prompty and Markdown files.")
console = Console()

# 隠しディレクトリ名 (バージョン履歴の保存場所)
HIDDEN_DIR = ".prompts"

# --- Configuration (設定) ---

# Frontmatterを安全に書き込める拡張子のホワイトリスト
SUPPORTED_EXTENSIONS = {".prompty", ".md", ".markdown", ".mdx"}

# --- Templates (ファイル初期化用のひな形) ---

TEMPLATE_PROMPTY = """---
name: structured_extractor
description: Extract structured data using OpenAI Structured Outputs
version: 0.1.0
authors: []
tags: [json, extraction]
model:
  api: chat
  configuration:
    type: azure_openai
    azure_deployment: gpt-4o
  parameters:
    temperature: 0.1
    max_completion_tokens: 4096
    response_format:
      type: json_schema
      json_schema:
        name: extraction_result
        strict: true
        schema:
          type: object
          properties:
            summary:
              type: string
          required: ["summary"]
          additionalProperties: false
inputs:
  text:
    type: string
sample:
  text: "Sample text"
---
system:
You are a helpful AI assistant.

user:
{{text}}
"""

TEMPLATE_BASIC = """---
name: new_prompt
version: 0.1.0
description: A new prompt file
---

Write your prompt here.
"""

TEMPLATES = {
    "prompty": TEMPLATE_PROMPTY,
    "basic": TEMPLATE_BASIC,
    "empty": "",
}

# --- Utils (ユーティリティ関数群) ---

def find_project_root(start_path: Path) -> Path:
    """
    現在のパスから親ディレクトリを遡り、プロジェクトのルートディレクトリを特定します。
    
    Args:
        start_path (Path): 探索を開始するディレクトリパス。

    Returns:
        Path: 特定されたプロジェクトルート。見つからない場合は start_path を返します。
    """
    markers = [".git", "pyproject.toml", "package.json", ".prompts"]
    current = start_path.resolve()
    for parent in [current] + list(current.parents):
        for marker in markers:
            if (parent / marker).exists():
                return parent
    return start_path

def get_store_path(target_file: Path) -> Path:
    """
    対象ファイルの履歴を保存するためのディレクトリパス（.prompts内）を生成します。
    プロジェクトルートからの相対パス構造を維持します。

    Args:
        target_file (Path): 履歴管理対象のファイルパス。

    Returns:
        Path: 履歴保存先のディレクトリパス。
    """
    target_abs = target_file.resolve()
    root = find_project_root(target_abs)
    try:
        # プロジェクトルートからの相対パスを取得して構造をミラーリング
        rel_path = target_abs.relative_to(root)
    except ValueError:
        # ルート外ファイルの場合は直下に作成
        return target_file.parent / HIDDEN_DIR / target_file.name
    return root / HIDDEN_DIR / rel_path

def load_meta(store_path: Path) -> List[Dict]:
    """
    保存先ディレクトリから meta.json を読み込みます。

    Args:
        store_path (Path): 履歴保存先のディレクトリパス。

    Returns:
        List[Dict]: 履歴データのリスト。ファイルがない場合は空リストを返します。
    """
    meta_file = store_path / "meta.json"
    if not meta_file.exists():
        return []
    with open(meta_file, "r", encoding="utf-8") as f:
        return json.load(f)

def save_meta(store_path: Path, data: List[Dict]):
    """
    履歴データを meta.json に保存します。

    Args:
        store_path (Path): 履歴保存先のディレクトリパス。
        data (List[Dict]): 保存する履歴データのリスト。
    """
    with open(store_path / "meta.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_latest_version(history: List[Dict]) -> str:
    """
    履歴リストから最新のバージョン番号を取得します。

    Args:
        history (List[Dict]): 履歴データのリスト。

    Returns:
        str: 最新のバージョン文字列（例: "0.1.0"）。履歴がない場合は "0.0.0"。
    """
    if not history:
        return "0.0.0"
    return history[0]["version"]

def parse_version(ver: str) -> Tuple[int, int, int]:
    """
    バージョン文字列を比較可能な整数のタプルに変換します。
    
    Args:
        ver (str): バージョン文字列 (例: "1.2.3")。

    Returns:
        Tuple[int, int, int]: (Major, Minor, Patch) のタプル。
    """
    try:
        parts = list(map(int, ver.split(".")))
        # 桁数が足りない場合は0で埋める (例: "1.0" -> (1, 0, 0))
        if len(parts) < 3:
            parts += [0] * (3 - len(parts))
        return tuple(parts[:3])
    except ValueError:
        return (0, 0, 0)

def extract_version_from_file(file_path: Path) -> Optional[str]:
    """
    ファイルのYAML Frontmatterから `version` フィールドの値を抽出します。

    Args:
        file_path (Path): 対象ファイルのパス。

    Returns:
        Optional[str]: バージョン文字列。見つからない場合は None。
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Frontmatterブロック(---\n...---)を抽出
    match = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if match:
        fm_content = match.group(1)
        # version: x.x.x を抽出
        ver_match = re.search(r'^version:\s*([\d\.]+)', fm_content, re.MULTILINE)
        if ver_match:
            return ver_match.group(1).strip()
    return None

def update_file_version(file_path: Path, new_version: str) -> bool:
    """
    ファイルのYAML Frontmatter内にある `version` フィールドを更新します。
    Frontmatterがない場合は新規作成します。

    Args:
        file_path (Path): 対象ファイルのパス。
        new_version (str): 設定する新しいバージョン文字列。

    Returns:
        bool: 更新が成功したかどうか。
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Frontmatterブロックを3つのグループで抽出 (開始区切り, 中身, それ以降)
    fm_match = re.search(r'^(---\s*\n)(.*?)(\n---\s*\n.*)', content, re.DOTALL)
    
    if fm_match:
        start_sep = fm_match.group(1)
        fm_body = fm_match.group(2)
        rest_of_file = fm_match.group(3)
        
        # 既存のversionキーがある場合は置換、なければ追記
        if re.search(r'^version:', fm_body, re.MULTILINE):
            new_fm_body = re.sub(r'^(version:\s*)([\d\.]+)', f'\\g<1>{new_version}', fm_body, flags=re.MULTILINE)
        else:
            new_fm_body = f"version: {new_version}\n{fm_body}"
            
        new_content = start_sep + new_fm_body + rest_of_file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True
    else:
        # Frontmatterがない場合はファイルの先頭に追加
        new_content = f"---\nversion: {new_version}\n---\n" + content
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True

# --- Commands (CLIコマンド群) ---

@app.command()
def init(
    file: Path,
    template: str = typer.Option(None, "--template", "-t", help="Template name (built-in key) or path to an existing file."),
):
    """
    ファイルの変更追跡を開始します（初期化）。
    テンプレートを指定して新規ファイルを作成することも可能です。
    """
    # 1. 拡張子チェック
    if file.suffix not in SUPPORTED_EXTENSIONS:
        console.print(f"[bold red]Error:[/bold red] File extension '{file.suffix}' is not supported.")
        console.print(f"Supported extensions: [cyan]{', '.join(sorted(SUPPORTED_EXTENSIONS))}[/cyan]")
        raise typer.Exit(1)

    store_path = get_store_path(file)
    
    # すでに管理下にあるか確認
    if (store_path / "meta.json").exists():
        console.print(f"[yellow]Already tracking {file}.[/yellow]")
        return
    
    store_path.mkdir(parents=True, exist_ok=True)

    # .gitignoreの生成 (promptsディレクトリ内をGit管理対象外にする設定)
    # ※ ユーザー指定により生成機能を維持
    internal_gitignore = store_path / ".gitignore"
    if not internal_gitignore.exists():
        with open(internal_gitignore, "w", encoding="utf-8") as f:
            f.write("*\n")
    
    # 2. コンテンツの準備（テンプレート処理）
    content_to_write = None
    is_template_used = False

    if template:
        template_path = Path(template)
        # A. テンプレートが既存ファイルパスの場合
        if template_path.exists() and template_path.is_file():
            console.print(f"[dim]Reading template from file: {template_path}[/dim]")
            with open(template_path, "r", encoding="utf-8") as f:
                content_to_write = f.read()
            is_template_used = True
        # B. テンプレートが内部キーワードの場合
        elif template in TEMPLATES:
            content_to_write = TEMPLATES[template]
            is_template_used = True
        else:
            console.print(f"[bold red]Error:[/bold red] Template '{template}' not found (neither a file nor a built-in key).")
            raise typer.Exit(1)

    # 3. ファイル作成 (存在しない場合のみ)
    if not file.exists():
        console.print(f"[cyan]Creating {file} ...[/cyan]")
        
        # テンプレート未指定時のデフォルト動作
        if content_to_write is None:
            if file.suffix == ".prompty":
                content_to_write = TEMPLATES["prompty"]
            else:
                content_to_write = TEMPLATES["basic"]

        with open(file, "w", encoding="utf-8") as f:
            f.write(content_to_write)
    
    elif is_template_used:
        # ファイルが存在するがテンプレート指定があった場合の警告
        console.print(f"[yellow]File {file} already exists. Using existing content instead of template.[/yellow]")

    # 4. バージョンの初期化 (0.1.0)
    initial_ver = "0.1.0"
    update_file_version(file, initial_ver)

    initial_entry = {
        "version": initial_ver,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "message": "Initial commit",
        "filename": f"v{initial_ver}_{file.name}"
    }
    
    # 初期スナップショットの保存
    shutil.copy(file, store_path / initial_entry["filename"])
    save_meta(store_path, [initial_entry])

    console.print(f"[green]Initialized {file} at version {initial_ver}[/green]")


@app.command()
def save(
    file: Path,
    message: str = typer.Option(..., "-m", "--message", help="Commit message"),
    major: bool = False,
    minor: bool = False,
    patch: bool = False,
):
    """
    現在の状態を新しいバージョンとして保存します。
    ファイル内容に変更がない場合の警告や、手動バージョン変更の検知を行います。
    """
    store_path = get_store_path(file)
    if not store_path.exists():
        console.print(f"[red]Not initialized. Run 'init {file}' first.[/red]")
        raise typer.Exit(1)

    history = load_meta(store_path)
    latest_meta_ver_str = get_latest_version(history)
    meta_ver = parse_version(latest_meta_ver_str)

    # --- 1. 変更検知ロジック (Change Detection) ---
    if history:
        last_filename = history[0]["filename"]
        last_file_path = store_path / last_filename
        
        # 最新スナップショットと現在のファイルをバイナリ比較
        if last_file_path.exists():
            with open(file, "rb") as f_curr, open(last_file_path, "rb") as f_last:
                if f_curr.read() == f_last.read():
                    console.print("[yellow]Warning: No changes detected since the last snapshot.[/yellow]")
                    # 強制保存するかユーザーに確認
                    if not typer.confirm("Do you want to force save a new version?"):
                        console.print("Aborted.")
                        raise typer.Abort()

    # --- 2. バージョン不整合の解消 (Version Conflict Handling) ---
    current_file_ver_str = extract_version_from_file(file)
    
    # ファイルにバージョン記述がない、またはパースできない場合はメタデータを正とする
    if current_file_ver_str is None:
        file_ver = meta_ver
        current_file_ver_str = latest_meta_ver_str
    else:
        file_ver = parse_version(current_file_ver_str)

    # 判定: ファイルのバージョンがメタデータより進んでいるか？ (ユーザーの手動書き換え検知)
    is_manual_bump = file_ver > meta_ver
    
    # 新しいバージョンの算出
    if is_manual_bump:
        console.print(f"[yellow]Manual version bump detected: {latest_meta_ver_str} -> {current_file_ver_str}[/yellow]")
        
        # フラグ指定がない場合 -> 手動変更を信頼してそのまま採用
        if not (major or minor or patch):
            new_ver_str = current_file_ver_str
        else:
            # フラグ指定がある場合 -> 手動変更されたバージョンを起点にさらにインクリメント
            cv = file_ver
            if major:
                nv = [cv[0] + 1, 0, 0]
            elif patch:
                nv = [cv[0], cv[1], cv[2] + 1]
            else:
                nv = [cv[0], cv[1] + 1, 0]
            new_ver_str = f"{nv[0]}.{nv[1]}.{nv[2]}"
            
    else:
        # 通常のフロー (metaバージョンを起点に自動インクリメント)
        cv = meta_ver
        if major:
            nv = [cv[0] + 1, 0, 0]
        elif patch:
            nv = [cv[0], cv[1], cv[2] + 1]
        else: # Default is minor
            nv = [cv[0], cv[1] + 1, 0]
        new_ver_str = f"{nv[0]}.{nv[1]}.{nv[2]}"

    # --- 保存処理 ---
    
    # バージョン文字列が変わる場合はファイルを更新して保存
    if new_ver_str != current_file_ver_str:
        console.print(f"Bumping version in file: [dim]{current_file_ver_str}[/dim] -> [bold cyan]{new_ver_str}[/bold cyan]")
        update_file_version(file, new_ver_str)
    else:
        console.print(f"Saving version: [bold cyan]{new_ver_str}[/bold cyan]")

    # スナップショットの作成
    artifact_name = f"v{new_ver_str}_{file.name}"
    shutil.copy(file, store_path / artifact_name)

    # メタデータの更新
    new_entry = {
        "version": new_ver_str,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "message": message,
        "filename": artifact_name
    }
    history.insert(0, new_entry)
    save_meta(store_path, history)

    console.print(f"[bold green]Saved {new_ver_str}[/bold green]: {message}")

@app.command("list")
def list_versions(file: Optional[Path] = typer.Argument(None, help="File to show history for. If empty, lists all tracked files.")):
    """
    指定されたファイルの履歴を表示するか、追跡中の全ファイル一覧を表示します。
    """
    # 引数 file が指定された場合 -> そのファイルの履歴詳細を表示
    if file:
        store_path = get_store_path(file)
        if not (store_path / "meta.json").exists():
            console.print(f"[red]No history found for {file}. Run 'init' first.[/red]")
            raise typer.Exit(1)

        history = load_meta(store_path)
        current_file_ver = None
        if file.exists():
            current_file_ver = extract_version_from_file(file)
        
        table = Table(title=f"History: {file.name}")
        table.add_column("Version", style="cyan", no_wrap=True)
        table.add_column("Time", style="dim")
        table.add_column("Message", style="white")

        for entry in history:
            ver = entry["version"]
            # 現在のファイルのバージョンと一致する行を強調
            is_current = (current_file_ver is not None and ver == current_file_ver)
            
            if is_current:
                ver_display = f"* {ver}"
                row_style = "bold green"
            else:
                ver_display = f"  {ver}"
                row_style = None

            table.add_row(ver_display, entry["timestamp"], entry["message"], style=row_style)

        console.print(table)
        return

    # 引数がない場合 -> プロジェクト内の全追跡ファイル一覧を表示
    root = find_project_root(Path.cwd())
    prompts_root = root / HIDDEN_DIR

    if not prompts_root.exists():
        console.print("[yellow]No .prompts directory found in this project.[/yellow]")
        return

    table = Table(title="All Tracked Prompts (Project Root)")
    table.add_column("File Path", style="bold yellow")
    table.add_column("Latest Ver", style="cyan")
    table.add_column("Last Modified", style="dim")

    found_any = False

    # 再帰的に meta.json を探して一覧化
    for meta_file in prompts_root.rglob("meta.json"):
        store_dir = meta_file.parent
        history = load_meta(store_dir)
        if not history:
            continue

        latest_ver = get_latest_version(history)
        last_mod = history[0]["timestamp"]

        try:
            display_path = store_dir.relative_to(prompts_root)
        except ValueError:
            display_path = store_dir.name

        table.add_row(str(display_path), latest_ver, last_mod)
        found_any = True

    if found_any:
        console.print(table)
    else:
        console.print("[yellow]No tracked prompts found.[/yellow]")

@app.command()
def diff(file: Path, version: str):
    """
    現在のファイル内容と、指定したバージョンのスナップショットとの差分を表示します。
    """
    store_path = get_store_path(file)
    history = load_meta(store_path)
    
    target_entry = next((item for item in history if item["version"] == version), None)
    if not target_entry:
        console.print(f"[red]Version {version} not found.[/red]")
        raise typer.Exit(1)

    target_file_path = store_path / target_entry["filename"]
    
    # Unified Diff を生成
    with open(target_file_path, "r", encoding="utf-8") as f:
        old_lines = f.readlines()
    with open(file, "r", encoding="utf-8") as f:
        new_lines = f.readlines()

    diff_gen = difflib.unified_diff(old_lines, new_lines, fromfile=f"v{version}", tofile="current", lineterm="")

    # 色付きで出力
    for line in diff_gen:
        if line.startswith("+"):
            console.print(line, style="green", end="")
        elif line.startswith("-"):
            console.print(line, style="red", end="")
        elif line.startswith("@"):
            console.print(line, style="cyan", end="")
        else:
            console.print(line, end="")

@app.command()
def checkout(file: Path, version: str):
    """
    指定したバージョンを現在のファイルに復元（チェックアウト）します。
    """
    store_path = get_store_path(file)
    history = load_meta(store_path)
    
    target_entry = next((item for item in history if item["version"] == version), None)
    if not target_entry:
        console.print(f"[red]Version {version} not found.[/red]")
        raise typer.Exit(1)

    src = store_path / target_entry["filename"]
    shutil.copy(src, file)
    console.print(f"[bold yellow]Restored {version} to {file}[/bold yellow]")

def cli():
    """CLIのエントリポイント"""
    app()

if __name__ == "__main__":
    cli()

