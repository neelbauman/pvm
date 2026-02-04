import pytest
from pathlib import Path
from typer.testing import CliRunner

@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def temp_project(tmp_path, monkeypatch):
    """
    テスト用の一時プロジェクトディレクトリを作成し、カレントディレクトリをそこに移動します。
    重要: プロジェクトルートとして正しく認識させるため、ダミーの .git ディレクトリを作成します。
    """
    project_dir = tmp_path / "my_project"
    project_dir.mkdir()
    
    # プロジェクトルートマーカー
    (project_dir / ".git").mkdir()
    
    monkeypatch.chdir(project_dir)
    return project_dir

@pytest.fixture
def mock_global_config(tmp_path, monkeypatch):
    """
    グローバル設定ディレクトリ (~/.config/pvm 等) を一時ディレクトリに向けます。
    """
    fake_config_dir = tmp_path / "fake_config"
    fake_config_dir.mkdir()
    
    # pvm.config モジュールの関数をモック
    def mock_get_dir():
        return fake_config_dir
        
    monkeypatch.setattr("pvm.config.get_global_config_dir", mock_get_dir)
    return fake_config_dir

