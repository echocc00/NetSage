# NetSage MCP Servers

每个 MCP server 独立部署（v2.0 二十六章），统一走 mcp-hub 网关对接 Agent。

## 安装

```bash
# shared 先装
cd mcp-servers/shared && pip install -e .

# 三个 server
cd mcp-servers/containerlab-mcp && pip install -e .
cd mcp-servers/batfish-mcp && pip install -e .
cd mcp-servers/napalm-mcp && pip install -e .
```

## 运行（stdio 模式）

```bash
python mcp-servers/containerlab-mcp/server.py
python mcp-servers/batfish-mcp/server.py
python mcp-servers/napalm-mcp/server.py
```

## 工具清单

### containerlab-mcp
- `deploy_topology(topo_yaml, name)` — 部署仿真拓扑
- `destroy_topology(name)` — 销毁
- `inspect_topology(name)` — 查看节点/链路
- `exec_on_node(name, node, command)` — 仿真内执行命令
- `save_topology(name, path)` — 保存为模板

### batfish-mcp
- `load_snapshot(configs_dir, snapshot_name)` — 加载配置快照
- `assert_reachability(snapshot, src, dst)` — 可达性断言
- `assert_acl(snapshot, acl_spec)` — ACL 断言
- `assert_routing(snapshot, prefix)` — 路由断言
- `lint_config(config_text, vendor)` — 语法 lint

### napalm-mcp
- `get_facts(vendor, host, ...)` — 设备 facts
- `get_config(vendor, host, source)` — 设备配置
- `load_merge_candidate(vendor, host, config)` — 加载候选
- `compare_config(vendor, host)` — diff
- `commit(vendor, host)` — 提交（写操作，须过三道闸）
- `discard(vendor, host)` — 丢弃候选

## 部署模式（v2.0 26.3）
- 开发态：sidecar（docker-compose 同 compose）
- 生产态：K8s Deployment + Service，独立扩缩容
