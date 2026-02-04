import json
import os
import stat
from pathlib import Path
from pvm.main import app

def test_lock_generates_file(runner, temp_project):
    """
    pvm lock コマンドが .pvm-lock.json を生成し、
    正しいバージョン情報が記録されていることを確認。
    """
    file_name = "test.prompty"
    
    # 1. Init (v0.1.0)
    runner.invoke(app, ["init", file_name, "--template", "basic"])
    
    # 2. Modify & Commit (v0.2.0)
    Path(file_name).write_text("Updated Content", encoding="utf-8")
    runner.invoke(app, ["commit", file_name])
    
    # 3. Lock
    result = runner.invoke(app, ["lock"])
    assert result.exit_code == 0
    
    lock_path = temp_project / ".pvm-lock.json"
    assert lock_path.exists()
    
    with open(lock_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["version"] == 1
        assert file_name in data["files"]
        assert data["files"][file_name]["version"] == "0.2.0"
        assert "hash" in data["files"][file_name]

def test_sync_restores_version(runner, temp_project):
    """
    pvm sync コマンドが、ロックファイルの内容に従って
    ファイルを復元することを確認（Git Checkout後のシミュレーション）。
    """
    file_name = "restore_me.md"
    file_path = temp_project / file_name
    
    # 1. Create v0.1.0 and v0.2.0
    runner.invoke(app, ["init", file_name]) # v0.1.0
    
    file_path.write_text("Version 2 Content", encoding="utf-8")
    runner.invoke(app, ["commit", file_name]) # v0.2.0
    
    # 2. Lock at v0.2.0
    runner.invoke(app, ["lock"])
    
    # 3. Simulate Git Checkout (Revert file to old state or garbage)
    file_path.write_text("Old v1 content or drift", encoding="utf-8")
    
    # 4. Sync
    result = runner.invoke(app, ["sync"])
    assert result.exit_code == 0
    assert "Sync complete" in result.stdout
    
    # 5. Verify Content matches v0.2.0 (Locked version)
    assert file_path.read_text("utf-8") == "Version 2 Content"

def test_sync_handles_missing_file(runner, temp_project):
    """
    ファイルが削除されていても sync で復活することを確認。
    """
    file_name = "deleted.md"
    runner.invoke(app, ["init", file_name])
    runner.invoke(app, ["lock"])
    
    # Delete file
    (temp_project / file_name).unlink()
    assert not (temp_project / file_name).exists()
    
    # Sync
    result = runner.invoke(app, ["sync"])
    assert result.exit_code == 0
    assert (temp_project / file_name).exists()

def test_status_detects_drift(runner, temp_project):
    """
    pvm status コマンドが、Lockファイルと現在のファイルの乖離（Drift）を
    正しく表示できるか確認。
    """
    file_name = "drift.md"
    f = temp_project / file_name
    
    # v0.1.0 Lock
    runner.invoke(app, ["init", file_name])
    runner.invoke(app, ["lock"])
    
    # Modify file without commit/lock -> Should be 'Drift' or 'Modified'
    # ケース1: 全く新しい内容 (Modified/Dirty)
    f.write_text("New Unknown Content")
    result = runner.invoke(app, ["status"])
    assert file_name in result.stdout
    assert "Modified" in result.stdout or "Drift" in result.stdout

    # ケース2: PVM履歴にあるがLockと違うバージョン (Drift)
    # v0.2.0 を作り、内容は v0.2.0 だが Lock は v0.1.0 のままの状態
    runner.invoke(app, ["commit", file_name]) # commit v0.2.0
    # Lock is still v0.1.0
    result = runner.invoke(app, ["status"])
    assert "Drift" in result.stdout 
    # Current Content は v0.2.0 と認識されるはず
    assert "0.2.0" in result.stdout

def test_hooks_install(runner, temp_project):
    """
    pvm hooks install が pre-commit フックを正しく生成するか。
    """
    # .git ディレクトリは conftest.py の temp_project で生成済み
    
    result = runner.invoke(app, ["hooks", "install"])
    assert result.exit_code == 0
    assert "Hook installed" in result.stdout
    
    hook_path = temp_project / ".git" / "hooks" / "pre-commit"
    assert hook_path.exists()
    
    # 実行権限の確認
    st = os.stat(hook_path)
    assert bool(st.st_mode & stat.S_IEXEC), "Hook script must be executable"
    
    # 内容の確認
    content = hook_path.read_text()
    assert "#!/bin/sh" in content
    assert "pvm lock" in content
    assert "git add .pvm-lock.json" in content

