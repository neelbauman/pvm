from pathlib import Path
from pvm import templates

def test_list_builtin_templates(mock_global_config):
    """組み込みテンプレートの確認"""
    avail = templates.get_available_templates()
    assert "azure" in avail
    assert "basic" in avail

def test_register_global_template(temp_project, mock_global_config):
    """ユーザー定義グローバルテンプレートの登録と取得"""
    my_tmpl = temp_project / "my_custom.prompty"
    my_tmpl.write_text("--- \nname: custom\n---", encoding="utf-8")
    
    templates.register_global_template(my_tmpl, name="special")
    
    expected_path = mock_global_config / "templates" / "special.prompty"
    assert expected_path.exists()
    
    avail = templates.get_available_templates()
    assert "special" in avail

def test_project_local_template_override(temp_project, mock_global_config):
    """プロジェクトローカルテンプレートの優先確認"""
    local_tmpl_dir = temp_project / ".prompts" / "templates"
    local_tmpl_dir.mkdir(parents=True)
    
    # basic テンプレートを上書き
    (local_tmpl_dir / "basic.md").write_text("Local Override")
    
    avail = templates.get_available_templates(temp_project)
    assert avail["basic"] == "Local Override"

