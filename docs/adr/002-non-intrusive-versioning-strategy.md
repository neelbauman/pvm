# 2. Non-Intrusive Versioning Strategy

Date: 2026-02-04
Status: Accepted

## Context
これまでの `pvm` は、管理対象ファイル（`.prompty` や `.md`）の YAML Frontmatter にある `version` フィールドを直接書き換えることでバージョン管理を行っていた。

しかし、以下の課題が顕在化していた：
1. Pythonスクリプト (`.py`) など、Frontmatter をネイティブにサポートしないファイル形式への対応が困難。
2. ツールがソースコードを自動的に書き換える挙動は、Linterとの競合、タイムスタンプの更新、予期しないGit差分の発生など、開発者体験（DX）を損なう副作用が大きい。

## Decision
我々は「非侵入型（Non-Intrusive）」のアプローチを採用する：

1. **Read-Only原則**: `pvm` は、デフォルトで管理対象ファイルへの書き込み（バージョンの注入）を行わない。
2. **Source of Truth**: バージョン情報の正本は、`.prompts/` ディレクトリ内のメタデータ (`meta.json`) のみとする。
3. **Global Ignore**: プロジェクトルートの `.prompts/.gitignore` に `*` を記述し、`pvm` の管理領域全体を Git の管理外とする。

## Consequences
### Positive
* `.py`, `.json`, `.txt` など、あらゆるテキストファイルを即座に管理可能になる。
* Git のコミット履歴がクリーンに保たれる（試行錯誤のノイズが混入しない）。
* ユーザーのコードに対する意図しない副作用がなくなる。

### Negative
* ファイル単体を開いた際、そのファイルがどのバージョンであるかが分からなくなる（`pvm list` での確認が必要）。
