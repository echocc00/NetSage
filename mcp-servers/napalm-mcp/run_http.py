"""以 streamable-http 启动 napalm-mcp（sidecar 部署，v2.0 二十六章 26.3）。

用法（容器或宿主机）：
    PYTHONPATH=/opt/mcp-servers/shared:/opt/mcp-servers/napalm-mcp \
    python3 run_http.py            # 默认 0.0.0.0:9003

环境变量：
    PORT          监听端口（默认 9003）
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
    port = int(os.getenv("PORT", "9003"))
    server.mcp.run(transport="http", host="0.0.0.0", port=port)
