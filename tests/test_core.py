import time
import shutil
from pathlib import Path
from rich.console import Console
from pvm import core

# 副作用をキャプチャしないダミーコンソール
console = Console(quiet=True)

def test_init_creates_structure(temp_project):
    """initが.promptsディレクトリと初期スナップショットを作成することを確認"""
    file_path = temp_project / "test_prompt.md"
    content = "Initial content"
    
    # ファイル作成 & init
    # Change: initialize_file -> create_new_file
    core.create_new_file(file_path, content, console)
    
    # .prompts ディレクトリの確認
    store_path = temp_project / ".prompts" / "test_prompt.md"
    assert store_path.exists()
    assert (store_path / "meta.json").exists()
    
    # スナップショットの確認
    history = core.load_meta(store_path)
    assert len(history) == 1
    assert history[0]["version"] == "0.1.0"
    
    snapshot_path = store_path / history[0]["filename"]
    assert snapshot_path.read_text("utf-8") == content

def test_global_gitignore_created(temp_project):
    """プロジェクトルートの .prompts/.gitignore が生成されるか"""
    file_path = temp_project / "foo.txt"
    # Change: initialize_file -> create_new_file
    core.create_new_file(file_path, "content", console)
    
    gitignore = temp_project / ".prompts" / ".gitignore"
    assert gitignore.exists()
    assert "*" in gitignore.read_text()

def test_commit_does_not_modify_source(temp_project):
    """
    【重要】commitしても元のファイルにバージョン情報が書き込まれないことを確認 (ADR-002)
    """
    file_path = temp_project / "script.py"
    initial_content = "print('hello')"
    
    # 1. Init
    # Change: initialize_file -> create_new_file
    core.create_new_file(file_path, initial_content, console)
    
    # 2. 編集
    time.sleep(0.01) # タイムスタンプ更新のため
    new_content = "print('hello world')"
    file_path.write_text(new_content, encoding="utf-8")
    
    # 3. Commit (Default Minor Update: 0.1.0 -> 0.2.0)
    core.commit_file(file_path, "update script", False, False, False, console)
    
    # バージョン確認
    store_path = core.get_store_path(file_path)
    history = core.load_meta(store_path)
    assert history[0]["version"] == "0.2.0"
    
    # ソースファイル確認: メタデータが注入されていないこと
    current_content = file_path.read_text("utf-8")
    assert "version:" not in current_content
    assert current_content == new_content

def test_list_status_missing(temp_project):
    """ファイルが削除された場合に 'exists': False が返るか"""
    file_path = temp_project / "lost.md"
    # Change: initialize_file -> create_new_file
    core.create_new_file(file_path, "content", console)
    
    # ファイルを削除
    file_path.unlink()
    
    # リスト取得
    results = core.list_all_tracked_files(temp_project)
    target = next(r for r in results if r["path"] == "lost.md")
    
    assert target["exists"] is False
    assert target["latest_version"] == "0.1.0"

def test_checkout_restores_deleted_directory(temp_project):
    """
    親ディレクトリごと削除されていても checkout で復元できるか
    """
    # 深い階層のファイルを作成
    file_path = temp_project / "src" / "prompts" / "deep.prompty"
    file_path.parent.mkdir(parents=True)
    # Change: initialize_file -> create_new_file
    core.create_new_file(file_path, "original", console)
    
    # 親ディレクトリごと削除 (rm -rf src/prompts)
    shutil.rmtree(temp_project / "src")
    assert not file_path.exists()
    
    # Checkout (Restore)
    # Improved: confirm=False を使ってロジックを直接テスト
    core.checkout_file(file_path, "0.1.0", console, confirm=False)
    
    assert file_path.exists()
    assert file_path.read_text("utf-8") == "original"

