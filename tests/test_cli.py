import shutil
from pathlib import Path
from pvm.main import app

def test_cli_init_and_commit(runner, temp_project):
    """Init -> Commit (Minor Update) のフロー"""
    file_name = "chat.prompty"
    
    # 1. Init
    result = runner.invoke(app, ["init", file_name, "--template", "basic"])
    assert result.exit_code == 0
    assert Path(file_name).exists()
    
    # 2. Modify & Commit
    Path(file_name).write_text("Modified", encoding="utf-8")
    result = runner.invoke(app, ["commit", file_name, "-m", "First update"])
    
    assert result.exit_code == 0
    # Default is Minor update (0.1.0 -> 0.2.0)
    assert "Committed 0.2.0" in result.stdout

def test_cli_list_status(runner, temp_project):
    """listコマンドでのステータス表示 (Active/Missing)"""
    # 2つのファイルを作成
    runner.invoke(app, ["init", "active.md"])
    runner.invoke(app, ["init", "missing.md"])
    
    # 1つ削除
    (temp_project / "missing.md").unlink()
    
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    
    # 出力チェック
    assert "active.md" in result.stdout
    assert "Active" in result.stdout # ステータス
    
    assert "missing.md" in result.stdout
    assert "Missing" in result.stdout # ステータス

def test_cli_checkout_restore(runner, temp_project):
    """checkoutコマンドによるディレクトリごとの復元"""
    file_path = Path("subdir/deep/test.md")
    file_path.parent.mkdir(parents=True)
    
    runner.invoke(app, ["init", str(file_path)])
    
    # ディレクトリごと削除
    shutil.rmtree("subdir")
    assert not file_path.exists()
    
    # Checkout (input='y' to confirm)
    result = runner.invoke(app, ["checkout", str(file_path), "0.1.0"], input="y\n")
    
    assert result.exit_code == 0
    assert "Restored" in result.stdout
    assert file_path.exists() # ファイルが復活していること

def test_cli_template_cmds(runner, temp_project, mock_global_config):
    """template add / list コマンド"""
    tmpl = temp_project / "t.txt"
    tmpl.write_text("content")
    
    # Add
    result = runner.invoke(app, ["template", "add", "t.txt", "--name", "my_t"])
    assert result.exit_code == 0
    
    # List
    result = runner.invoke(app, ["template", "list"])
    assert "my_t" in result.stdout

