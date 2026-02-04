import json
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table

from . import core, templates, config

# アプリケーション定義
app = typer.Typer(help="Simple Prompt Version Manager (Non-intrusive)")
template_app = typer.Typer(help="Manage custom templates")
hooks_app = typer.Typer(help="Manage Git hooks for automatic locking")

app.add_typer(template_app, name="template")
app.add_typer(hooks_app, name="hooks")

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
    Create a NEW file from a template and start tracking it.
    Automatically creates parent directories if they don't exist.
    """
    # テンプレートの解決
    context_dir = file.parent if file.parent.exists() else Path.cwd()
    avail_templates = templates.get_available_templates(context_dir)
    
    target_template = template
    if not target_template:
        target_template = templates.get_default_template_name(file.suffix)
        
    content_to_write = ""
    if target_template in avail_templates:
        content_to_write = avail_templates[target_template]
        console.print(f"[dim]Using template: {target_template}[/dim]")
    else:
         if target_template != "basic":
            console.print(f"[yellow]Template '{target_template}' not found. Using empty file/basic.[/yellow]")
         console.print(f"Available: {', '.join(avail_templates.keys())}")
    
    # 新規作成処理
    core.create_new_file(file, content_to_write, console)

@app.command(name="track")
def track(file: Path):
    """
    Start tracking an EXISTING file.
    """
    core.track_existing_file(file, console)

@app.command(name="add", hidden=True)
def add_cmd(file: Path):
    """Alias for 'track'"""
    core.track_existing_file(file, console)

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
    Show history for a file, or list all tracked files.
    """
    if file:
        # --- File History Mode ---
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
        # --- Project Overview Mode ---
        root = config.find_project_root(Path.cwd())
        tracked_files = core.list_all_tracked_files(root)

        if not tracked_files:
            console.print("[yellow]No tracked files found.[/yellow]")
            return

        table = Table(title="All Tracked Files")
        table.add_column("Status", no_wrap=True)
        table.add_column("File Path", style="bold yellow")
        table.add_column("Latest Ver", style="cyan")
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

# --- Lock File & Sync Commands (v1.0.0) ---

@app.command()
def lock():
    """
    Generate or update the .pvm-lock.json file.
    Use this before 'git commit' to record current prompt versions.
    """
    core.create_lock_file(console)

@app.command()
def sync():
    """
    Restore prompt versions from .pvm-lock.json.
    Use this after 'git checkout/pull' to sync pvm state.
    """
    core.sync_from_lock_file(console)

@app.command()
def status():
    """
    Show status of tracked files including lock state and drift.
    """
    root = config.find_project_root(Path.cwd())
    
    # 1. Load Lock File
    lock_file = root / core.LOCK_FILE_NAME
    lock_map = {}
    if lock_file.exists():
        try:
            with open(lock_file, "r", encoding="utf-8") as f:
                lock_map = json.load(f).get("files", {})
        except Exception:
            pass
            
    # 2. List Tracked Files
    tracked_files = core.list_all_tracked_files(root)
    if not tracked_files:
        console.print("[yellow]No tracked files.[/yellow]")
        return
        
    table = Table(title="PVM Status (Drift Check)")
    table.add_column("File", style="bold")
    table.add_column("Lock Ver", style="dim")
    table.add_column("Current Content", style="cyan")
    table.add_column("Status")

    for item in tracked_files:
        rel_path = item["path"]
        full_path = root / rel_path
        store_path = root / config.HIDDEN_DIR / rel_path
        
        # Lock Version
        lock_info = lock_map.get(rel_path)
        lock_ver_str = lock_info["version"] if lock_info and lock_info["version"] else "-"
        
        # Current Content Version (Identify by hash)
        current_content_ver = "-"
        status_str = ""
        
        if not full_path.exists():
            status_str = "[red]Missing[/red]"
        else:
            identified = core.identify_version_by_content(full_path, store_path)
            if identified:
                current_content_ver = identified
                if lock_ver_str != "-" and lock_ver_str != identified:
                    status_str = "[yellow]Drift[/yellow]" # Lockと実体が違う
                elif lock_ver_str == identified:
                    status_str = "[green]Synced[/green]"
                else:
                    status_str = "[blue]Active[/blue]" # Lock未登録だが実体は既知のVer
            else:
                current_content_ver = "(Dirty)"
                status_str = "[yellow]Modified[/yellow]" # どのバージョンとも一致しない

        table.add_row(rel_path, lock_ver_str, current_content_ver, status_str)
        
    console.print(table)

# --- Hooks Commands ---

@hooks_app.command("install")
def install_hooks_cmd():
    """
    Install Git pre-commit hook to automatically run 'pvm lock'.
    """
    core.install_hooks(console)

# --- Template Commands ---

@template_app.command("list")
def list_templates():
    """List all available templates."""
    avail = templates.get_available_templates(Path.cwd())
    table = Table(title="Available Templates")
    table.add_column("Name", style="cyan")
    table.add_column("Source", style="dim")
    
    for name in avail.keys():
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

