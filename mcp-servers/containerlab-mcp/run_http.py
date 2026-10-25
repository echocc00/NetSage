"""以 streamable-http 启动 containerlab-mcp（sidecar 部署，v2.0 二十六章 26.3）。

用法（容器内）：
    PYTHONPATH=/opt/mcp-servers/shared:/opt/mcp-servers/containerlab-mcp \
    python3 run_http.py            # 默认 0.0.0.0:9001

环境变量：
    PORT          监听端口（默认 9001）
    CLAB_BIN      containerlab 二进制（默认 containerlab）
    CONTAINERLAB_HOST  远程 SSH 模式（见 server.py）
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SHARED = _HERE.parent / "shared"
for p in (str(_SHARED), str(_HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import server  # noqa: E402

if __name__ == "__main__":
    port = int(os.getenv("PORT", "9001"))
    server.mcp.run(transport="http", host="0.0.0.0", port=port)
