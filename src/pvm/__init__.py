import json
import shutil
import difflib
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Simple Prompt Version Manager")
console = Console()

HIDDEN_DIR = ".prompts"

# --- Utils ---
# --- Utils ---

def find_project_root(start_path: Path) -> Path:
    """
    .git, .hg, pyproject.toml などがある場所をルートとみなす。
    見つからなければ現在のディレクトリを返す。
    """
    # 探索対象のマーカー
    markers = [".git", "pyproject.toml", "package.json", ".prompts"]
    
    current = start_path.resolve()
    for parent in [current] + list(current.parents):
        for marker in markers:
            if (parent / marker).exists():
                return parent
    return start_path

def get_store_path(target_file: Path) -> Path:
    """
    集中管理型のパスを生成する。
    例: 
      Root: /app
      File: /app/src/backend/prompt.prompty
      -> /app/.prompts/src/backend/prompt.prompty/ (ここに meta.json 等が入る)
    """
    target_abs = target_file.resolve()
    root = find_project_root(target_abs)
    
    # プロジェクト外のファイルを指定された場合のガード
    try:
        rel_path = target_abs.relative_to(root)
    except ValueError:
        # ルート外なら、そのファイルの親ディレクトリに .prompts を作る（フォールバック）
        return target_file.parent / HIDDEN_DIR / target_file.name

    # .prompts/元のパス構造/ファイル名/
    return root / HIDDEN_DIR / rel_path

# load_meta, save_meta など他の関数はそのまま維持

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

def parse_version(ver: str):
    return list(map(int, ver.split(".")))

def extract_version_from_file(file_path: Path) -> Optional[str]:
    """ファイル内の Frontmatter から version を読み取る"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Frontmatterブロック (--- で囲まれた部分) を探す
    match = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if match:
        fm_content = match.group(1)
        # version: x.y.z を探す
        ver_match = re.search(r'^version:\s*([\d\.]+)', fm_content, re.MULTILINE)
        if ver_match:
            return ver_match.group(1).strip()
    return None

def update_file_version(file_path: Path, new_version: str) -> bool:
    """ファイル内の version: ... を正規表現で安全に書き換える"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Frontmatterブロックの検出
    fm_match = re.search(r'^(---\s*\n)(.*?)(\n---\s*\n.*)', content, re.DOTALL)
    
    if fm_match:
        start_sep = fm_match.group(1)
        fm_body = fm_match.group(2)
        rest_of_file = fm_match.group(3)
        
        # versionキーがあるか確認
        if re.search(r'^version:', fm_body, re.MULTILINE):
            # 既存のversionを置換
            new_fm_body = re.sub(
                r'^(version:\s*)([\d\.]+)', 
                f'\\g<1>{new_version}', 
                fm_body, 
                flags=re.MULTILINE
            )
        else:
            # versionがない場合は先頭に追加
            new_fm_body = f"version: {new_version}\n{fm_body}"
            
        new_content = start_sep + new_fm_body + rest_of_file
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True
    else:
        # Frontmatter自体がない場合、ファイルの先頭に追加する
        new_content = f"---\nversion: {new_version}\n---\n" + content
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True

# --- Commands ---

@app.command()
def init(file: Path):
    """Start tracking a file. Creates a robust template with JSON Schema in Frontmatter."""
    
    store_path = get_store_path(file)
    
    if (store_path / "meta.json").exists():
        console.print(f"[yellow]Already tracking {file}.[/yellow]")
        return
    
    store_path.mkdir(parents=True, exist_ok=True)

    internal_gitignore = store_path / ".gitignore"
    if not internal_gitignore.exists():
        with open(internal_gitignore, "w", encoding="utf-8") as f:
            f.write("*\n")
    
    # --- ここをアップデート ---
    if not file.exists():
        console.print(f"[cyan]File {file} not found. Creating structured template...[/cyan]")
        
        # JSON Schema を Frontmatter (parameters) に埋め込む
        default_content = """---
name: structured_extractor
description: Extract structured data using OpenAI Structured Outputs
version: 0.1.0
authors: []
tags: [json, extraction, structured-output]
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
              description: "A concise summary of the input text (1-2 sentences)."
            keywords:
              type: array
              items:
                type: string
              description: "Key topics extracted from the text."
            sentiment:
              type: string
              enum: ["positive", "neutral", "negative"]
              description: "The overall sentiment of the text."
            entities:
              type: array
              items:
                type: object
                properties:
                  name:
                    type: string
                  type:
                    type: string
                    description: "Person, Organization, Location, etc."
                required: ["name", "type"]
                additionalProperties: false
          required: ["summary", "keywords", "sentiment", "entities"]
          additionalProperties: false
inputs:
  text:
    type: string
sample:
  text: "Microsoft released a new AI tool called Prompty. It helps developers manage prompts as assets."
---
system:
You are a helpful AI assistant.
The user will provide text, and you must extract information according to the strict JSON schema defined in the response_format.

user:
{{text}}
"""
        with open(file, "w", encoding="utf-8") as f:
            f.write(default_content)

    # ファイル内のバージョンを確認
    file_ver = extract_version_from_file(file)
    initial_ver = file_ver if file_ver else "0.1.0"
    
    # ファイルにバージョンが無ければ書き込む
    if not file_ver:
        console.print(f"[cyan]Adding version: {initial_ver} to file...[/cyan]")
        update_file_version(file, initial_ver)

    # 初期エントリ作成
    initial_entry = {
        "version": initial_ver,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "message": "Initial commit",
        "filename": f"v{initial_ver}_{file.name}"
    }
    
    # 現状のファイルをコピー
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
    """Update file version, save content, and record snapshot."""
    store_path = get_store_path(file)
    if not store_path.exists():
        console.print(f"[red]Not initialized. Run 'init {file}' first.[/red]")
        raise typer.Exit(1)

    history = load_meta(store_path)
    current_ver_str = get_latest_version(history)
    cv = parse_version(current_ver_str)

    # 1. 新しいバージョン番号を決定
    if major:
        nv = [cv[0] + 1, 0, 0]
    elif patch:
        nv = [cv[0], cv[1], cv[2] + 1]
    else: # Default is minor
        nv = [cv[0], cv[1] + 1, 0]
    
    new_ver_str = f"{nv[0]}.{nv[1]}.{nv[2]}"
    
    # 2. ファイルの中身を書き換える (Source of Truthの更新)
    console.print(f"Bumping version in file: [dim]{current_ver_str}[/dim] -> [bold cyan]{new_ver_str}[/bold cyan]")
    update_file_version(file, new_ver_str)

    # 3. 書き換えたファイルをスナップショットとして保存
    artifact_name = f"v{new_ver_str}_{file.name}"
    shutil.copy(file, store_path / artifact_name)

    # 4. メタデータ更新
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
    """Show version history or list all tracked files."""
    
    # 1. 特定のファイルの履歴を表示する場合
    if file:
        store_path = get_store_path(file)
        if not (store_path / "meta.json").exists():
            console.print(f"[red]No history found for {file}. Run 'init' first.[/red]")
            raise typer.Exit(1)

        history = load_meta(store_path)
        
        table = Table(title=f"History: {file.name}")
        table.add_column("Version", style="cyan", no_wrap=True)
        table.add_column("Time", style="dim")
        table.add_column("Message", style="white")

        for entry in history:
            table.add_row(entry["version"], entry["timestamp"], entry["message"])

        console.print(table)
        return

    # 2. 全ファイルをリスト表示する場合 (引数なし)
    # どこで実行しても、現在のプロジェクトルートを探しに行く
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

    # .prompts 以下を再帰的に探索し、meta.json があるディレクトリを探す
    for meta_file in prompts_root.rglob("meta.json"):
        store_dir = meta_file.parent
        history = load_meta(store_dir)
        
        if not history:
            continue

        latest_ver = get_latest_version(history)
        last_mod = history[0]["timestamp"]

        # ストアパスから、元のファイルパスを逆算して表示用に整形
        # store_dir: /app/.prompts/src/backend/prompt.md
        # relative:  src/backend/prompt.md
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
    """Diff current file against a specific version."""
    store_path = get_store_path(file)
    history = load_meta(store_path)
    
    target_entry = next((item for item in history if item["version"] == version), None)
    if not target_entry:
        console.print(f"[red]Version {version} not found.[/red]")
        raise typer.Exit(1)

    target_file_path = store_path / target_entry["filename"]
    
    with open(target_file_path, "r", encoding="utf-8") as f:
        old_lines = f.readlines()
    with open(file, "r", encoding="utf-8") as f:
        new_lines = f.readlines()

    diff_gen = difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"{version}", tofile="current",
        lineterm=""
    )

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
    """Restore a specific version to current file."""
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
    app()

