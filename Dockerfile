# Dockerfile
# =============================================================================
# MCPサーバーをDocker化する際の注意点
# =============================================================================
#
# ■ docker run のオプション設定（重要）
# ---------------------------------------------------------------------------
# 正しい設定:
#   docker run -i --rm --init shellserver-mcp
#
# 間違った設定（接続失敗）:
#   docker run -it --rm shellserver-mcp
#              ↑ -t が問題
#
# ■ 各オプションの意味
# ---------------------------------------------------------------------------
#   | オプション          | 必須度 | 意味                                   |
#   |--------------------|--------|----------------------------------------|
#   | -i                 | 必須   | stdin を開いたままにする               |
#   | -t                 | 禁止   | 疑似TTY（端末）を割り当てる            |
#   | --rm               | 任意   | コンテナ終了時に自動削除               |
#   | --init             | 推奨   | PID 1 として init プロセスを使用       |
#   | -e KEY=VALUE       | 任意   | 環境変数を設定                         |
#
# ※ 接続成功の決め手は「-t を外すこと」
#    -e DOCKER_CONTAINER=true は MCP 接続には無関係（任意の環境変数）
#
# -e DOCKER_CONTAINER=true の用途（任意）:
#   - アプリ内で「Docker環境で動作しているか」を判定したい場合に使う
#   - 例: os.environ.get("DOCKER_CONTAINER") で確認
#   - パスやログ出力先の切り替えなどに使える
#
# ■ なぜ -t があると接続失敗するのか
# ---------------------------------------------------------------------------
# MCPの通信方式: stdio（標準入出力）でJSON-RPCを送受信
#
#   Claude Code ←→ stdin/stdout ←→ MCPサーバー
#
# -t（TTY）があると:
#   - 改行コードの変換（LF → CRLF）
#   - 制御文字の解釈
#   - エコーバック
#   - バッファリングの変更
#
# これらがJSON-RPCプロトコルを壊すため、通信が失敗する。
#
# 【-i のみ（成功）】
#   Claude Code → 純粋なJSON → Docker stdin → MCPサーバー
#
# 【-it（失敗）】
#   Claude Code → 純粋なJSON → TTY(変換) → MCPサーバー
#                                 ↑ データが壊れる
#
# ■ --init の役割
# ---------------------------------------------------------------------------
# --init なし: PID 1 = python → シグナル処理が不完全、ゾンビプロセス発生
# --init あり: PID 1 = tini → 適切なシグナル処理、子プロセスの reap
#
# ■ Claude Code での設定例（~/.claude.json）
# ---------------------------------------------------------------------------
#   "terminal-server-docker": {
#     "command": "docker",
#     "args": ["run", "-i", "--rm", "--init", "-e", "DOCKER_CONTAINER=true", "shellserver-mcp"]
#   }
#
# =============================================================================

# Use an official Python runtime as a parent image
FROM python:3.12-slim-bookworm

# Install uv using the official distroless image.
# Pinning to a specific version (e.g., :0.6.11) is recommended for reproducibility.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set the working directory in the container
WORKDIR /app

# Copy project definition (pyproject.toml) and lock file (if available)
# Assumes pyproject.toml exists in your project root (shellserver).
# If you generate and use a lock file (uv.lock), uncomment the second COPY line for reproducible builds.
COPY pyproject.toml ./
COPY uv.lock ./

# Install dependencies using uv sync.
# Leverages Docker layer caching via --mount=type=cache.
# --frozen ensures installs match the lock file (if provided and copied). Remove if no lock file.
# --no-install-project skips installing the local project code in this layer, optimizing caching.
# NOTE: This command relies on 'pyproject.toml' correctly listing dependencies, including 'mcp'.
# Ensure the 'mcp' package is resolvable based on your project setup (see pyproject.toml notes).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Copy the application code into the container
COPY server.py .
COPY main.py .
# If you decided to vendor the 'mcp' package (copying it into shellserver), uncomment the next line:
# COPY ./mcp ./mcp

# Install the project itself using uv sync.
# This step makes your 'shellserver' project available in the environment managed by uv.
# Use --frozen if you have a lock file copied.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

# Define the command to run the application using 'uv run'
CMD ["uv", "run", "main.py"]