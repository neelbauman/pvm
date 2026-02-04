import typer
from pathlib import Path

# アプリケーション定数
APP_NAME = "pvm"
HIDDEN_DIR = ".prompts"

def get_global_config_dir() -> Path:
    """
    OS標準のユーザー設定ディレクトリを取得します。
    (例: ~/.config/pvm on Linux/Mac, AppData/Local/pvm on Windows)
    """
    path = Path(typer.get_app_dir(APP_NAME))
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_global_template_dir() -> Path:
    """ユーザー定義のグローバルテンプレート保存先を取得します。"""
    path = get_global_config_dir() / "templates"
    path.mkdir(parents=True, exist_ok=True)
    return path

def find_project_root(start_path: Path) -> Path:
    """
    現在のパスから親ディレクトリを遡り、プロジェクトのルートディレクトリを特定します。
    """
    markers = [".git", "pyproject.toml", "package.json", HIDDEN_DIR]
    current = start_path.resolve()
    for parent in [current] + list(current.parents):
        for marker in markers:
            if (parent / marker).exists():
                return parent
    
    # フォールバック修正:
    # ファイル自身(または拡張子付きの存在しないパス)が渡された場合、その親ディレクトリを返す
    if start_path.is_file() or (not start_path.exists() and start_path.suffix):
        return start_path.parent
        
    return start_path

