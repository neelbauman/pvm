# Prompt Version Manager

LLMプロンプト開発（Prompt Engineering）における**「試行錯誤」の履歴を、Gitのコミット履歴を汚さずにローカルで管理するためのCLIツール**です。

`.prompty` や `.md` ファイルのYAML Frontmatterに含まれる `version` フィールドを自動的に解析・更新し、スナップショットを保存します。

## 🌟 特徴

* **Git履歴の分離**: プロンプトの微調整（"temperatureを0.1下げた"、"few-shotを1つ追加した"など）をGitコミットせず、専用の `.prompts` ディレクトリで管理します。
* **Frontmatter統合**: ファイル内の `version: x.x.x` を自動的に読み書きします。
* **手動変更の優先 (Manual Precedence)**: エディタで直接 `version` を書き換えた場合、ツールはそれを検知し、その手動バージョンを正として採用します。
* **変更検知**: 内容に変更がない場合の無駄な保存を防ぎます。
* **テンプレート機能**: `.prompty` のボイラープレートを自動生成して素早く書き始められます。
* **RichなUI**: `rich` ライブラリによる見やすいテーブル表示と、色分けされたDiff表示。

## 📦 必要要件

* Python 3.10+
* [Typer](https://typer.tiangolo.com/)
* [Rich](https://rich.readthedocs.io/)

## 🚀 インストール

1. git clone します。
   ```bash
   git clone https://github.com/neelbauman/pvm.git
   ```

2. uvで依存関係共々ツールとしてインストールするのが楽です。
    ```bash
    cd pvm
    uv tool install .

    # pvmが使えるようになっているはず
    pvm --help

    ```


## 📖 使い方

### 1. 初期化 (`init`)

ファイルを追跡対象にします。ファイルが存在しない場合はテンプレートから作成します。

```bash
# 基本的な初期化
pvm init my_prompt.prompty

# テンプレートを指定して作成（prompty, basic, empty が利用可能）
pvm init new_task.md --template basic

# 既存ファイルをテンプレートとして指定することも可能（バージョンは初期化される）
pvm init super_task.md -t new_task.md

```

### 2. 保存 (`save`)

現在の状態をスナップショットとして保存し、バージョンを上げます。

```bash
# マイナーバージョンアップ (デフォルト: 0.1.0 -> 0.2.0)
pvm save my_prompt.prompty -m "制約条件を追加"

# パッチバージョンアップ (0.1.0 -> 0.1.1)
pvm save my_prompt.prompty -m "Typo修正" --patch

# メジャーバージョンアップ (0.1.0 -> 1.0.0)
pvm save my_prompt.prompty -m "プロンプト構造を大幅に変更" --major

```

**💡 手動バージョン変更の挙動:**
エディタで `my_prompt.prompty` のバージョンを直接 `0.5.0` に書き換えてから `save` コマンドを実行すると、ツールは自動採番を行わず、手動で指定された `0.5.0` を採用して保存します。

### 3. 履歴の確認 (`list`)

ファイルのバージョン履歴を表示します。

```bash
# プロジェクト内の管理されている全ファイルを表示
pvm list

# 特定のファイルの履歴を表示
pvm list my_prompt.prompty

```

### 4. 差分確認 (`diff`)

現在のファイルと、過去のバージョンとの差分を表示します。

```bash
# 現在のファイル vs バージョン 0.1.0
pvm diff my_prompt.prompty 0.1.0

```

### 5. 復元 (`checkout`)

過去のバージョンを現在のファイルに書き戻します。

```bash
pvm checkout my_prompt.prompty 0.1.0

```

## 📂 ディレクトリ構造

管理データはプロジェクトルートの `.prompts` ディレクトリに保存されます。

```text
ProjectRoot/
├── my_prompt.prompty       # 作業中のファイル
├── .prompts/               # 隠しディレクトリ
│   ├── .gitignore          # 履歴ファイルをGitから除外
│   └── my_prompt.prompty/
│       ├── meta.json       # バージョンメタデータ
│       ├── v0.1.0_my_prompt.prompty
│       ├── v0.2.0_my_prompt.prompty
│       └── ...
└── ...

```

デフォルトでは `.prompts/.gitignore` に `*` が書き込まれ、履歴ファイルはGit管理対象外となります。チームで履歴を共有したい場合は、この `.gitignore` を編集してください。

## ✅ 対応フォーマット

以下の拡張子で、YAML Frontmatter (`--- ... ---`) を持つファイルをサポートしています。

* `.prompty`
* `.md`, `.markdown`, `.mdx`

```

