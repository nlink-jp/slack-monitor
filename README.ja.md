# slack-monitor

ローカル LLM またはクラウド LLM で動く、Slack チャンネルのリアルタイム活動要約ツール。

[stail](https://github.com/magifd2/stail) 経由で Slack チャンネルを監視し、いま何が起きて
いるか — 話題、センチメント、累積した発見事項、状況要約 — を定期的に要約して、ライブ TUI に
描画するか、Rich のパネルとして出力する。

## 2 つのコマンド

| コマンド | モード | 動作 |
|---------|------|--------------|
| `slack-monitor-tui` | TUI（既定） | 内部で stail を起動する。3 パネルのライブ表示 |
| `slack-monitor` | Plain | stail の JSONL を標準入力から読む。Rich のパネルを出力 |

## 必要なもの

- Python 3.12 以降
- [uv](https://docs.astral.sh/uv/)（パッケージマネージャ）
- [stail](https://github.com/magifd2/stail)（設定済みで、PATH 上にあること）
- OpenAI 互換の LLM API:
  - [LM Studio](https://lmstudio.ai/)（ローカル。開発用に推奨）
  - [litellm-proxy](https://docs.litellm.ai/docs/proxy/quick_start)（Vertex AI などを経由してクラウドモデルを使う場合）

## インストール

```bash
git clone <repo>
cd slack-monitor
uv sync --all-groups
```

## 設定

### 1. API キーを設定する（必須）

```bash
export SLACK_MONITOR_API_KEY="lm-studio"   # LM Studio の場合
export SLACK_MONITOR_API_KEY="your-key"    # クラウド API の場合
```

`OPENAI_API_KEY` をフォールバックとして使ってもよい。

> **セキュリティ:** API キーを `config.toml` に書かないこと。必ず環境変数を使う。

### 2. 設定ファイルを作る（任意）

```bash
cp config.toml.example config.toml
# 必要に応じて config.toml を編集する
```

主な設定:

| 設定 | 既定値 | 説明 |
|---------|---------|-------------|
| `[llm] base_url` | `http://localhost:1234/v1` | LLM API のエンドポイント |
| `[llm] model` | `openai/gpt-oss-20b` | モデル識別子 |
| `[buffer] window_seconds` | `60` | 分析の間隔（秒） |
| `[buffer] max_messages` | `50` | 1 回の分析バッチあたりの最大メッセージ数 |
| `[output] show_raw` | `false` | LLM の生の JSON 出力を表示する |

すべての設定は環境変数で上書きできる（`.env.example` を参照）。

### 3. LM Studio の準備

1. LM Studio をダウンロードして起動する
2. モデル `openai/gpt-oss-20b`（または互換するモデル）をロードする
3. ローカルサーバーを起動する（既定: `http://localhost:1234`）

### 4. litellm-proxy の準備（Vertex AI Gemini 向け）

```bash
litellm --model vertex_ai/gemini-2.0-flash --port 4000
```

続いて、次を設定する:
```bash
export SLACK_MONITOR_BASE_URL="http://localhost:4000/v1"
export SLACK_MONITOR_MODEL="vertex_ai/gemini-2.0-flash"
```

## 使い方

### TUI モード — `slack-monitor-tui`

内部で stail を起動する。パイプは不要。

```bash
# 基本的な使い方
slack-monitor-tui --channel "#general"

# stail へ追加の引数を渡す（例: 独自の設定ファイル）
slack-monitor-tui --channel "#general" --stail-args "--config myconfig.json"

# 分析ウィンドウを変える（30 秒）
slack-monitor-tui --channel "#general" --window 30

# 出力言語を固定する
slack-monitor-tui --channel "#general" --language Japanese

# LLM のモデルを上書きする
slack-monitor-tui --channel "#general" --model vertex_ai/gemini-2.0-flash

# デバッグログ
slack-monitor-tui --channel "#general" --debug
```

stail は次のように起動される:
```
stail tail -f -q --format json --channel <channel> [stail-args...]
```

終了するには **Ctrl+C** を押す。

### Plain モード — `slack-monitor`

stail の JSONL を標準入力から読む。stail の出力は自分でパイプする。

```bash
# 基本的な使い方
stail tail -f --format json -c "#general" | slack-monitor

# 出力にチャンネル名を付ける
stail tail -f --format json -c "#general" | slack-monitor --channel general

# LLM の生の JSON 出力を表示する
stail tail -f --format json -c "#general" | slack-monitor --show-raw

# デバッグモード
stail tail -f --format json -c "#general" | slack-monitor --debug
```

## 分析の出力

### TUI モード

3 パネル構成:

```
┌──────────────────────────────────────────────────────────────┐
│ slack-monitor  #general                          12:34:56    │  ← header
├─────────────────────┬────────────────────────────────────────┤
│ SYSTEM STATUS       │ 03/19 12:33:01 → 12:34:42  12 msgs     │
│                     │                                        │
│ Buffer  0 msgs      │ TOPICS  deployment, rollback           │
│ Next    45s         │ MOOD    negative   active              │
│ Status  waiting     │                                        │
│                     │ FINDINGS                               │
│                     │   [CRIT] Deploy #347 failed at 12:33   │
│                     │   [WARN] Rollback in progress          │
│                     │                                        │
│                     │ SITUATION                              │
│                     │ Production deploy failed; team is      │
│                     │ executing rollback procedure.          │
├─────────────────────┴────────────────────────────────────────┤
│ 12:33:01 @alice  deploy #347 started                        │
│ 12:33:42 @bob    it's failing, initiating rollback          │
└──────────────────────────────────────────────────────────────┘
```

**FINDINGS** は、分析ウィンドウをまたいで保持される、具体的な事実の累積リスト。
各項目には重大度のタグ `[INFO]` `[OK]` `[WARN]` `[ALRT]` `[CRIT]` が付く。
発見事項は無期限に残る — LLM にはすべてを引き継ぐよう指示しており、LLM がうっかり
落とした項目はクライアント側が自動で復元する。

**SITUATION** は、直近のウィンドウ全体を通した全体像の継続的な統合。
**THIS WIN**（SITUATION と内容が異なるときに、その下に表示される）は、現在のウィンドウで変化した分だけを述べる。

分析パネルの時刻範囲は、実際のメッセージのタイムスタンプ（ウィンドウ内の最初 → 最後の投稿）を反映する。

### Plain モード

分析ウィンドウごとに、Rich のパネルを標準出力へ出力する。

## 開発

```bash
# テストを実行する
uv run pytest

# 詳細出力でテストを実行する
uv run pytest -v

# テストファイルを 1 つだけ実行する
uv run pytest tests/test_llm.py
```

開発ルールとアーキテクチャの詳しい文書は [CLAUDE.md](CLAUDE.md) を参照。

## LLM に対する堅牢性

slack-monitor は、次のように振る舞いうるローカル LLM でも確実に動くよう設計されている:
- `<think>/<thinking>` ブロックを出力する（自動で除去する）
- 壊れた JSON を返す（波括弧の深さによる抽出 + 末尾カンマの修正）
- 書式が一定しない（多段のフォールバック連鎖）
- 文脈長が小さい（64K トークンの予算管理）

## セキュリティ

- API キーを設定ファイルやコードに保存することはない
- Slack のメッセージ本文は信頼できない入力として扱い、インジェクション対策のタグで囲む
- メッセージ内の URL は、LLM に送る前と表示の前に無害化する（`http://` → `hxxp://`）
- LLM には、発見事項や要約で言及するドメインや URL を無害化するよう指示する
- システムの境界（標準入力、LLM の出力、設定）すべてで入力を検証する
- セキュリティ方針の全文は [CLAUDE.md](CLAUDE.md) を参照

## ライセンス

MIT — [LICENSE](LICENSE) を参照。
