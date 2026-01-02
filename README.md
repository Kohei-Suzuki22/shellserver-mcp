# shellserver-mcp

MCP（Model Context Protocol）サーバーの学習用リポジトリです。
MCPサーバーの作成方法、async/await の動作、Docker化の注意点などを、実際のコードとコメントで学べます。

## 概要

このリポジトリでは、以下を学習できます：

- **MCP サーバーの基本構造**（FastMCP を使用）
- **Tool と Resource の違い**
- **async/await の動作原理**（I/O バウンド vs CPU バウンド）
- **Docker 化する際の注意点**（特に `-t` オプションの問題）

## リポジトリ構造

```
shellserver-mcp/
├── server.py        # MCPサーバー本体（詳細なコメント付き）
├── main.py          # エントリーポイント（トランスポート設定）
├── Dockerfile       # Docker化の設定と注意点
├── pyproject.toml   # プロジェクト設定
├── uv.lock          # 依存関係ロックファイル
└── README.md        # このファイル
```

## 提供する機能

### Tools

| ツール名 | 説明 |
|----------|------|
| `run_command` | ターミナルコマンドを実行し、stdout/stderr/return_code を返す |
| `benign_tool` | 外部URLからコンテンツをダウンロード（セキュリティ学習用） |

### Resources

| リソース名 | URI | 説明 |
|-----------|-----|------|
| `mcpreadme` | `file://mcpreadme` | デスクトップの mcpreadme.md を公開 |

## セットアップ

### 前提条件

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)（推奨）または pip

### インストール

```bash
# リポジトリをクローン
git clone https://github.com/Kohei-Suzuki22/shellserver-mcp.git
cd shellserver-mcp

# 依存関係をインストール（uv を使用）
uv sync
```

## 実行方法

### ローカル実行

```bash
uv run main.py
```

### Claude Code から使用

`~/.claude.json` に以下を追加：

```json
{
  "mcpServers": {
    "terminal-server": {
      "command": "uv",
      "args": ["run", "main.py"],
      "cwd": "/path/to/shellserver-mcp"
    }
  }
}
```

### Docker で実行

```bash
# イメージをビルド
docker build -t shellserver-mcp .

# 実行（重要: -t は使用しない）
docker run -i --rm --init shellserver-mcp
```

Claude Code から Docker 版を使用する場合：

```json
{
  "mcpServers": {
    "terminal-server-docker": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "--init", "shellserver-mcp"]
    }
  }
}
```

## 学習ポイント

### 1. async/await の動作

`server.py` には async/await の詳細な説明があります：

- **await は「ブロックせずに待つ」**: その行の処理が完了するまで下に進まないが、待機中は他のリクエストを処理できる
- **I/O バウンド処理に効果的**: ネットワーク、ファイル、外部コマンド実行など
- **CPU バウンド処理には効果なし**: asyncio はシングルスレッド。並列計算には `multiprocessing` が必要

```
【図解: async/await の効果】

同期（def + subprocess.run）:
  時間 →  0s     1s     2s     3s     4s     5s
  リクエストA: ████████████████████████████████████  sleep 5
  リクエストB:                                       ████ echo hi
                                                     ↑ Aが終わるまで待機

非同期（async + await）:
  時間 →  0s     1s     2s     3s     4s     5s
  リクエストA: ████████████████████████████████████  sleep 5
  リクエストB: ████                                   echo hi
               ↑ Aのawait中に処理される！
```

### 2. Tool と Resource の違い

| 項目 | Tool | Resource |
|------|------|----------|
| 用途 | アクション実行 | データ提供 |
| 例 | コマンド実行、API呼出 | ファイル内容、設定値 |
| 副作用 | あり得る | 基本的になし（読み取り専用） |
| REST類似 | POST | GET |

### 3. Claude Code での確認方法

| 確認方法 | Tool | Resource |
|----------|------|----------|
| `/mcp` コマンド | ○ | ✕ |
| `@` メンション | - | ✕（個別取得のみ） |
| Claude に「一覧見せて」と頼む | ○ | ○ |

### 4. Docker 化の注意点

MCP サーバーを Docker 化する際、`docker run` のオプションに注意：

| オプション | 必須度 | 説明 |
|-----------|--------|------|
| `-i` | **必須** | stdin を開いたままにする |
| `-t` | **禁止** | TTY が JSON-RPC プロトコルを壊す |
| `--init` | 推奨 | シグナル処理の改善 |
| `--rm` | 任意 | コンテナ自動削除 |

```bash
# 正しい
docker run -i --rm --init shellserver-mcp

# 間違い（接続失敗）
docker run -it --rm shellserver-mcp
```

### 5. トランスポート方式

| 方式 | 用途 | 通信方法 |
|------|------|----------|
| `stdio` | ローカル環境 | 標準入出力 |
| `streamable-http` | リモート公開 | HTTP + ストリーミング |

Claude Desktop の `command` + `args` 形式では `stdio` が必須。

## セキュリティに関する注意

`benign_tool` は「無害なツール」という名前ですが、実際には外部 URL からコンテンツをダウンロードします。
これは **ツール名だけを信用してはいけない** という教訓を示すデモです。

MCP サーバーを使用する際は、必ず **実装を確認** してください。
