import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table

from . import core, templates, config

# アプリケーション定義
app = typer.Typer(help="Simple Prompt Version Manager (Non-intrusive)")
template_app = typer.Typer(help="Manage custom templates")
app.add_typer(template_app, name="template")

console = Console()

# --- Main Commands ---

@app.command()
def init(
    file: Path,
    template: str = typer.Option(
        None, "-t", "--template", 
        help="Template name to use. See 'pvm template list'."
    ),
):
    """
    Start tracking a file. If file doesn't exist, create it from a template.
    """
    # テンプレートの解決
    content_to_write = ""
    if not file.exists():
        # カレントディレクトリ(またはファイルの親)を基準にテンプレートを探す
        avail_templates = templates.get_available_templates(file.parent)
        
        target_template = template
        if not target_template:
            target_template = templates.get_default_template_name(file.suffix)
            
        if target_template in avail_templates:
            content_to_write = avail_templates[target_template]
            console.print(f"[dim]Using template: {target_template}[/dim]")
        else:
            # 該当テンプレートがない場合は警告を出してbasicを使うなどの処理
            # ここではエラーメッセージを出して候補を表示
            if target_template != "basic":
                console.print(f"[yellow]Template '{target_template}' not found. Using empty file/basic.[/yellow]")
            console.print(f"Available: {', '.join(avail_templates.keys())}")
            
    core.initialize_file(file, content_to_write, console)

@app.command(name="commit")
def commit_cmd(
    file: Path,
    message: Optional[str] = typer.Option(None, "-m", "--message", help="Commit message"),
    major: bool = False,
    minor: bool = False,
    patch: bool = False,
):
    """
    Commit changes to version history.
    """
    core.commit_file(file, message, major, minor, patch, console)

@app.command("list")
def list_versions(file: Optional[Path] = typer.Argument(None)):
    """
    Show history for a file, or list all tracked files with their status.
    """
    if file:
        # --- File History Mode (Single File) ---
        store_path = core.get_store_path(file)
        if not (store_path / "meta.json").exists():
            console.print(f"[red]No history for {file}[/red]")
            raise typer.Exit(1)
            
        history = core.load_meta(store_path)
        table = Table(title=f"History: {file.name}")
        table.add_column("Version", style="cyan")
        table.add_column("Time", style="dim")
        table.add_column("Message")
        
        for i, entry in enumerate(history):
            is_latest = (i == 0)
            ver = f"* {entry['version']}" if is_latest else f"  {entry['version']}"
            style = "bold green" if is_latest else None
            table.add_row(ver, entry["timestamp"], entry["message"], style=style)
        console.print(table)
    else:
        # --- Project Overview Mode (All Files) ---
        root = config.find_project_root(Path.cwd())
        
        # Coreロジックを使って一覧を取得
        tracked_files = core.list_all_tracked_files(root)

        if not tracked_files:
            console.print("[yellow]No tracked files found.[/yellow]")
            return

        table = Table(title="All Tracked Files")
        table.add_column("Status", no_wrap=True)
        table.add_column("File Path", style="bold yellow")
        table.add_column("Latest", style="cyan")
        table.add_column("Last Modified", style="dim")

        for item in tracked_files:
            if item["exists"]:
                status = "[green]Active[/green]"
            else:
                status = "[red]Missing[/red]"
            
            table.add_row(
                status,
                item["path"], 
                item["latest_version"], 
                item["last_modified"]
            )
        console.print(table)

@app.command()
def diff(file: Path, version: str):
    """Show diff between current file and a specific version."""
    core.diff_file(file, version, console)

@app.command()
def checkout(file: Path, version: str):
    """Restore a specific version (overwrites current file)."""
    core.checkout_file(file, version, console)

# --- Template Commands ---

@template_app.command("list")
def list_templates():
    """List all available templates."""
    avail = templates.get_available_templates(Path.cwd())
    table = Table(title="Available Templates")
    table.add_column("Name", style="cyan")
    table.add_column("Source", style="dim")
    
    for name in avail.keys():
        # Source判定 (簡易的)
        if name in templates.BUILTINS:
            source = "Built-in"
        else:
            source = "Custom"
        table.add_row(name, source)
    console.print(table)

@template_app.command("add")
def add_template(
    file: Path = typer.Argument(..., exists=True, help="Source file"),
    name: str = typer.Option(None, help="Template name (default: filename)")
):
    """Register a file as a global custom template."""
    dest = templates.register_global_template(file, name)
    console.print(f"[green]Template registered:[/green] {dest.stem}")
    console.print(f"[dim]Location: {dest}[/dim]")

def cli():
    app()

if __name__ == "__main__":
    cli()

