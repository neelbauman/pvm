# 7. Lock File for Reproducibility

Date: 2026-02-04
Status: Accepted

## Context
`pvm` は非侵入型（Non-Intrusive）の管理を行うため、`.prompts/` ディレクトリは `.gitignore` によって Git の管理対象外とされている。
これにより、Git で過去のコミットにチェックアウトした際、ワークツリー上のファイルは過去の状態に戻るが、`pvm` の内部状態（どのバージョンがアクティブか）は最新のまま維持されるという「乖離（Drift）」が発生する。
これにより、過去のバージョンの再現性（Reproducibility）が損なわれる問題がある。

## Decision
Git のコミットと `pvm` のバージョン情報を紐付けるための「接着剤」として、ロックファイルを導入する。

1.  **Lock File (`.pvm-lock.json`)**:
    * 現在チェックアウトされているファイルのバージョン情報を記録する JSON ファイル。
    * プロジェクトルートに配置し、**Git の管理対象とする**。
    * 形式: `{ "files": { "path/to/file": { "version": "1.0.0", "hash": "..." } } }`

2.  **Commands**:
    * `pvm lock`: 現在の `pvm` の状態をロックファイルに書き出す。
    * `pvm sync`: ロックファイルの情報を基に、`pvm` の内部状態（チェックアウト状態）を復元する。
    * `pvm status`: ワークツリー、ロックファイル、`pvm` 履歴の3者間の乖離を表示する。

3.  **Automation**:
    * `pvm hooks install`: Git の `pre-commit` フックをセットアップし、コミット時に自動的に `pvm lock` を実行・更新する仕組みを提供する。

## Consequences
### Positive
* Git のコミットハッシュとプロンプトのバージョンが厳密に紐付き、完全な再現性が保証される。
* チーム開発において、`git pull` 後に `pvm sync` するだけで環境が同期される。
* CI/CD パイプラインで特定のプロンプトバージョンを確実に指定できるようになる。

### Negative
* `pvm` の管理ファイルの一部（ロックファイル）が Git 管理下に入るため、完全な "Non-Intrusive" ではなくなる（許容範囲とする）。
* Git の操作（Checkout/Pull）後に `pvm sync` を忘れると乖離が発生する（`pvm status` で緩和する）。

