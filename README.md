# pvm (Prompt Version Manager)

**プロンプトのための、ちいさなバージョン管理ツール。**

`pvm` は、LLMプロンプトを主要なユースケース対象として設計された軽量で非侵入型のバージョン管理ツールです。
ソースファイル自体を書き換えることなく、プロンプトファイル（`.prompty`, `.py`, `.md` など）の変更履歴を追跡します。

Gitと併用して使う、「超強力なローカル履歴管理」や「Undo/Redo」のようなものだと考えてください。

## ✨ 主な特徴

* **非侵入型 (Non-Intrusive)**: あなたのソースコードには一切触れません。メタデータの注入や、YAML Frontmatterの書き換えは行いません。
* **あらゆるファイルに対応**: Pythonスクリプト、Markdown、JSON、SQL、そしてもちろん `.prompty` も。テキストファイルなら何でも管理できます。
* **きれいなGit履歴**: 試行錯誤の履歴は隠しディレクトリ `.prompts/` で管理されるため、メインのGit履歴を汚しません。
* **堅牢な復元機能**: ファイルやディレクトリごと削除してしまっても、`pvm checkout` で構造ごと復元できます。
* **テンプレートシステム**: 組み込みテンプレート（`azure`, `openai`）や、独自のカスタムテンプレートを使って素早くプロンプト作成を開始できます。

## 📦 インストール

Python 3.9以上が必要です。

```bash
# pipでインストール (公開後)
pip install pvm-cli

# または uv を使用してインストール
uv tool install .

```

## 🚀 はじめ方

### 1. 新規プロジェクト / 新規ファイルの作成 (`init`)

テンプレートから新しいプロンプトファイルを作成します。親ディレクトリが存在しない場合は自動的に作成されます。

```bash
# Azure OpenAI スタイルのプロンプトを新規作成
pvm init my_agent/chat.prompty --template azure

# シンプルなMarkdownプロンプトを新規作成
pvm init ideas/draft.md --template basic

```

### 2. 既存ファイルの追跡開始 (`track`)

すでに手元にあるファイルを管理対象に追加します。

```bash
pvm track scripts/legacy_prompt.py
# エイリアス: pvm add

```

### 3. バージョンの保存 (`commit`)

気が向いたときにいつでもバージョンを保存しましょう。些細な変更でGitのコミットログを汚す心配はありません。

```bash
pvm commit chat.prompty -m "システムプロンプトを微調整"
pvm commit chat.prompty --major -m "全面的な書き直し"

```

### 4. 履歴とステータスの確認 (`list`)

管理中のファイル一覧と、その状態（`Active`: 存在する / `Missing`: 削除された）を確認できます。

```bash
# 管理中の全ファイル一覧を表示
pvm list

# 特定のファイルの履歴詳細を表示
pvm list chat.prompty

```

### 5. バージョンの復元 (`checkout`)

過去の任意のバージョンに戻せます。ファイル（あるいはそのディレクトリごと）削除されていても、`pvm` が再構築して復元します。

```bash
# バージョン 0.1.0 に復元
pvm checkout chat.prompty 0.1.0

```

## 🎨 テンプレートシステム

`pvm` は以下の優先順位でテンプレートを探します：

1. **プロジェクトローカル**: `<ProjectRoot>/.prompts/templates/` (チーム内での標準化に最適)
2. **ユーザーグローバル**: `~/.config/pvm/templates/` (個人のコレクション)
3. **組み込み (Built-in)**: `azure`, `openai`, `basic`

```bash
# 利用可能なテンプレート一覧を表示
pvm template list

# 既存のファイルをカスタムテンプレートとして登録
pvm template add my_best_prompt.prompty --name my_standard

```

## 📂 仕組み

`pvm` は、すべてのバージョン履歴をプロジェクトルートの隠しディレクトリ `.prompts/` に保存します。

```text
my_project/
├── .prompts/
│   ├── .gitignore         # .prompts/ 内をすべてGit対象外にします
│   ├── chat.prompty/
│   │   ├── meta.json      # バージョンメタデータ
│   │   ├── v0.1.0_chat.prompty
│   │   └── v0.2.0_chat.prompty
│   └── ...
├── chat.prompty           # あなたの作業ファイル (pvmは書き換えません)
└── main.py

```

`.prompts/.gitignore` が自動生成されるため、細かい履歴（`pvm`のデータ）をGitにコミットしてしまう心配はありません。
ワークツリーにある `chat.prompty` などの正本だけをGitで管理できます。

## 🛠️ 開発

このプロジェクトは依存関係管理に `uv` を使用しています。

```bash
# テストの実行
uv run pytest

# コードフォーマット
uv run ruff format

```

## ライセンス

MIT

