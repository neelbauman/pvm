# 4. Layered Template Resolution System

Date: 2026-02-04
Status: Accepted

## Context
ユーザーは `.prompty` (Azure/OpenAI) だけでなく、独自のフォーマットでプロンプト開発を開始したいと考えている。
ハードコードされたテンプレートだけでは柔軟性が低く、またチームや個人で共通のテンプレートを使い回したいという要求に対応できない。

## Decision
テンプレートを以下の優先順位で探索・解決する「階層構造」を採用する：

1. **Project Local**: `<ProjectRoot>/.prompts/templates/` (チーム共有用)
2. **User Global**: `~/.config/pvm/templates/` (個人用)
3. **Built-in**: ソースコード内のデフォルト定義 (Azure/Basic等)

また、`pvm template add` コマンドにより、任意のファイルを User Global 領域に登録可能にする。

## Consequences
### Positive
* ユーザーは `pvm init -t my_custom` のように、自分やチームの資産を簡単に再利用できる。
* プロジェクトごとに推奨されるプロンプト形式を強制・共有しやすくなる。

### Negative
* 適用されたテンプレートがどの層から読み込まれたかをユーザーが意識する必要がある（`pvm template list` でソースを表示することで緩和する）。
