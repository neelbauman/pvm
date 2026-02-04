# pvm (Prompt Version Manager)

**プロンプトのための、ちいさなバージョン管理ツール。**

`pvm` は、LLMプロンプトを主要なユースケース対象として設計された軽量で非侵入型のバージョン管理ツールです。
ソースファイル自体を書き換えることなく、プロンプトファイル（`.prompty`, `.py`, `.md` など）の変更履歴を追跡します。

Gitと併用して使う、「小規模なローカル履歴管理」や「Undo/Redo」のようなものだと考えてください。

## ✨ 主な特徴

* **非侵入型 (Non-Intrusive)**: あなたのソースコードには一切触れません。メタデータの注入や、YAML Frontmatterの書き換えは行いません。
* **あらゆるファイルに対応**: Pythonスクリプト、Markdown、JSON、SQL、そしてもちろん `.prompty` も。テキストファイルなら何でも管理できます。
* **きれいなGit履歴**: 試行錯誤の履歴は隠しディレクトリ `.prompts/` で管理されるため、メインのGit履歴を汚しません。
* **完全な再現性 (v1.0.0+)**: `.pvm-lock.json` により、Gitのコミットとプロンプトのバージョンを厳密に紐付け、過去の状態を完璧に復元できます。
* **テンプレートシステム**: 組み込みテンプレート（`azure`, `openai`）や、独自のカスタムテンプレートを使って素早くプロンプト作成を開始できます。

## 📦 インストール

Python 3.9以上が必要です。

```bash
git clone https://github.com/neelbauman/pvm.git
cd pvm

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

## 🔒 Gitとの連携 (再現性の確保) [New in v1.0.0]

Gitで過去のコミットに戻った際、`pvm` のプロンプトバージョンも自動的に同期させることで、**完全な環境の再現**が可能になります。

### 自動連携のセットアップ (推奨)

プロジェクトのセットアップ時に一度だけ実行してください。Gitの `pre-commit` フックをインストールし、コミット時に自動的にロックファイル (`.pvm-lock.json`) を更新します。

```bash
pvm hooks install

```

### 過去のバージョンへの同期 (`sync`)

`git checkout` や `git pull` でコードベースを過去の状態（あるいは最新の状態）に変更した後、以下のコマンドを実行します。

```bash
# 1. Gitでコードを移動
git checkout HEAD~5

# 2. PVMの状態を同期（ロックファイルの内容に合わせて復元）
pvm sync

```

### 手動でのロック (`lock`)

フックを使用しない場合は、Gitコミットの前に手動でロックファイルを更新してください。

```bash
pvm lock
git add .pvm-lock.json
git commit -m "feat: update prompts"

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
├── .pvm-lock.json         # [v1.0.0] Git管理対象のロックファイル
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
ワークツリーにある `chat.prompty` などの正本と、`.pvm-lock.json` だけをGitで管理します。

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

