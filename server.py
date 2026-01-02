from mcp.server.fastmcp import FastMCP
import subprocess
import asyncio
from typing import Optional, Dict, Any, List


# =============================================================================
# MCPサーバーインスタンスの作成
# =============================================================================
# "terminal-server" はサーバーの識別名
# MCPクライアント（Claude Desktop等）がこのサーバーを認識する際に使用される
mcp = FastMCP("terminal-server")


# =============================================================================
# ツールの定義
# =============================================================================
# @mcp.tool() デコレータ:
#   - この関数をMCPツールとして登録する
#   - クライアントから呼び出し可能になる
#
# async を使う理由（推奨だが必須ではない）:
#   1. MCPサーバーは内部的にasyncioで動作している
#   2. I/O操作（コマンド実行、ファイル読み書き等）で待ち時間が発生する
#   3. asyncを使うと、待ち時間中に他のリクエストを処理できる
#   4. 同期関数も使えるが、重い処理があると他の処理がブロックされる
#
# 同期関数の例（これも動作する）:
#   @mcp.tool()
#   def simple_tool(text: str) -> str:
#       return text.upper()
#
@mcp.tool()
async def run_command(command: str) -> Dict[str, Any]:
  """
  Run a terminal command and return the output.

  ↑ このdocstringがMCPクライアント側で表示されるツールの説明（description）になる
    - Claude Desktopなどでツール一覧を見た時に表示される
    - AIがどのツールを使うか判断する際の情報源になる
    - 分かりやすく具体的に書くことが重要

  Args:
    command: The command to execute in the terminal.
             ↑ 引数の説明もクライアントに渡される（パラメータのdescription）

  Returns:
    A dictionary containing stdout, stderr, and return code.
  """
  try:
    # -------------------------------------------------------------------------
    # await の意味: 「ブロックせずに待つ」
    # -------------------------------------------------------------------------
    # Q: 全部awaitしてるなら結局順番に実行されるのでは？
    # A: このリクエスト内では順番だが、サーバー全体では並行処理される
    #
    # 例：
    #   クライアントA: run_command("sleep 5")  ← 5秒のawait中...
    #   クライアントB: run_command("echo hi")  ← Aのawait中にBを処理！
    #
    # awaitで待機中、Pythonのイベントループは：
    #   - このタスクを一時停止
    #   - 他のタスク（別リクエスト）を処理
    #   - I/O完了後、このタスクを再開
    #
    # もし同期関数（def + subprocess.run）だと：
    #   - 5秒間サーバー全体がブロック
    #   - その間、他のリクエストは一切処理できない
    #
    # 【図解】
    #
    # 同期（def + subprocess.run）:
    #   時間 →  0s     1s     2s     3s     4s     5s
    #   リクエストA: ████████████████████████████████████  sleep 5
    #   リクエストB:                                       ████ echo hi
    #                                                      ↑ Aが終わるまで待機
    #
    # 非同期（async + await）:
    #   時間 →  0s     1s     2s     3s     4s     5s
    #   リクエストA: ████████████████████████████████████  sleep 5
    #   リクエストB: ████                                   echo hi
    #                ↑ Aのawait中に処理される！
    #
    # ポイント:
    #   - await = 「自分は待つけど、他の人はどうぞ」
    #   - 同期  = 「自分が終わるまで誰も動くな」
    #
    # -------------------------------------------------------------------------
    # awaitの基本動作
    # -------------------------------------------------------------------------
    # awaitは「その行の処理が完了するまで下の行を実行しない」
    #
    #   process = await create_subprocess_shell(...)  ← 完了まで待つ
    #   stdout, stderr = await process.communicate()  ← 上が終わってから実行
    #   return {...}                                  ← 上が終わってから実行
    #
    # awaitの2つの側面:
    #   | 側面           | 説明                                   |
    #   |----------------|----------------------------------------|
    #   | この関数内     | 下の行に進まない（順番に実行）         |
    #   | サーバー全体   | 待ち時間中、他のリクエストを処理できる |
    #
    # → 「自分の処理は順番だけど、待ってる間は他の人に譲る」
    #
    # -------------------------------------------------------------------------
    # 注意: async/await は CPUバウンドな処理には効果がない
    # -------------------------------------------------------------------------
    # Pythonのasyncioはシングルスレッドで動作する
    #
    #   | 処理タイプ     | async/await | 複数CPU活用              |
    #   |----------------|-------------|--------------------------|
    #   | I/Oバウンド    | 効果あり    | 不要（待ち時間を有効活用）|
    #   | CPUバウンド    | 効果なし    | multiprocessingが必要    |
    #
    # 4vCPU + async でも1コアしか使わない（シングルスレッドだから）
    # CPUをフルに使う計算処理を並列化するには multiprocessing を使う
    # -------------------------------------------------------------------------

    # Execute the command (非同期でサブプロセス作成)
    process = await asyncio.create_subprocess_shell(
      command,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
    )

    # Get output (コマンド完了を非同期で待機)
    stdout, stderr = await process.communicate()

    # Retrun results
    return {
      "stdout": stdout.decode() if stdout else "",
      "stderr": stderr.decode() if stderr else "",
      "return_code": process.returncode,
    }

  except Exception as e:
    return {
      "stdout": "",
      "stderr": f"Error executing command: {str(e)}",
      "return_code": -1
    }

