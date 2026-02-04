import shutil
from pathlib import Path
from typing import Dict, Optional
from .config import get_global_template_dir, find_project_root, HIDDEN_DIR

# --- Built-in Templates ---

TEMPLATE_AZURE = """---
name: structured_extractor
description: Extract structured data using Azure OpenAI
version: 0.1.0
model:
  api: chat
  configuration:
    type: azure_openai
    azure_deployment: gpt-4o
  parameters:
    temperature: 0.1
    response_format: { type: json_schema }
inputs:
  text:
    type: string
---
system:
You are a helpful AI assistant.

user:
{{text}}
"""

TEMPLATE_OPENAI = """---
name: simple_chat
description: Standard OpenAI Chat
version: 0.1.0
model:
  api: chat
  configuration:
    type: openai
    model: gpt-4o
  parameters:
    temperature: 0.7
inputs:
  question:
    type: string
---
system:
You are a helpful assistant.

user:
{{question}}
"""

TEMPLATE_BASIC = """---
name: new_prompt
version: 0.1.0
description: A new prompt file
---

Write your prompt here.
"""

BUILTINS = {
    "azure": TEMPLATE_AZURE,
    "azure_openai": TEMPLATE_AZURE,
    "openai": TEMPLATE_OPENAI,
    "basic": TEMPLATE_BASIC,
}

DEFAULT_TEMPLATE_BY_EXT = {
    ".prompty": "azure",
    ".md": "basic",
    ".markdown": "basic",
    ".mdx": "basic",
}

# --- Template Management Logic ---

def get_project_template_dir(current_path: Path) -> Optional[Path]:
    """プロジェクトローカルのテンプレートディレクトリ (.prompts/templates) を取得"""
    root = find_project_root(current_path)
    path = root / HIDDEN_DIR / "templates"
    if path.exists() and path.is_dir():
        return path
    return None

def get_available_templates(current_path: Path = Path.cwd()) -> Dict[str, str]:
    """
    利用可能な全テンプレートを取得します。
    優先順位: Project Local > User Global > Built-in
    """
    # 1. Built-in
    templates = BUILTINS.copy()
    
    # 2. User Global
    global_dir = get_global_template_dir()
    _load_templates_from_dir(global_dir, templates)
    
    # 3. Project Local
    local_dir = get_project_template_dir(current_path)
    if local_dir:
        _load_templates_from_dir(local_dir, templates)
            
    return templates

def _load_templates_from_dir(directory: Path, container: Dict[str, str]):
    """ディレクトリ内のファイルをテンプレートとして読み込みます"""
    if not directory.exists():
        return
    
    for path in directory.glob("*"):
        if path.is_file() and path.suffix in [".md", ".prompty", ".txt"]:
            key = path.stem # ファイル名をキーとする (my_tmpl.prompty -> my_tmpl)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    container[key] = f.read()
            except Exception:
                pass # 読み込みエラーは無視

def register_global_template(source_path: Path, name: str = None) -> Path:
    """指定されたファイルをグローバルテンプレートとして登録します"""
    global_dir = get_global_template_dir()
    
    if name is None:
        name = source_path.stem
        
    dest_path = global_dir / f"{name}{source_path.suffix}"
    shutil.copy(source_path, dest_path)
    return dest_path

def get_default_template_name(suffix: str) -> str:
    return DEFAULT_TEMPLATE_BY_EXT.get(suffix, "basic")

