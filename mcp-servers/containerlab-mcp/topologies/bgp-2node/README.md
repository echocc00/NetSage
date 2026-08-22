# bgp-2node · 2 节点 BGP 仿真拓扑

## 用途
W2 超最小演示的核心仿真验证（v2.0 开发计划十六章）。

## 结构
```
spine01 (AS65001, 10.0.0.1/30) ──eth1── leaf01 (AS65002, 10.0.0.2/30, lo 20.0.0.1/24)
```

## 运行
```bash
# WSL Ubuntu（root 权限）
cd /mnt/f/claudepc/NetSage/mcp-servers/containerlab-mcp/topologies
~/bin/containerlab deploy -t bgp-2node.clab.yaml
~/bin/containerlab inspect -c --label clab-node-lab-name=bgp-2node
~/bin/containerlab destroy --cleanup --label clab-node-lab-name=bgp-2node

# 进入节点验证
docker exec clab-bgp-2node-leaf01 vtysh -c 'show bgp summary'
```

## 镜像与环境
- 镜像：`frrouting/frr:latest`（DaoCloud 镜像源拉取，daemon 为 Ubuntu 内 docker）
- daemon：Ubuntu WSL 内 `service docker start`（与 Docker Desktop 引擎独立）
- clab 二进制：`~/bin/containerlab`（v0.78.2）
- 注意：WSL Ubuntu 需 root 运行 clab（`wsl -u root`）

## 已知问题（debug backlog）
### BGP 前缀未通告（20.0.0.0/24 到 spine）
- **现象**：邻居 Established（双侧摘要 MsgRcvd 持续增长），但 spine `show ip bgp` 为空，
  `show bgp neighbors` 显示 0 accepted prefixes；spine → 20.0.0.1 ping 100% 丢包
- **排查记录**：
  1. FRR 容器 `bgpd=no` 默认 → 已用自定义 daemons 修复（bgpd=yes）
  2. zebra 不应用 frr.conf 的 `interface lo/eth1 ip address` → 改为拓扑 exec 加地址（已生效，接口 ping 通）
  3. `network 20.0.0.0/24` 与 `redistribute connected` 均未触发送出前缀
  4. exec 时机晚于 bgpd 启动（clab exec 在容器创建后），`clear ip bgp *` 后 leaf 本地表出现 best 前缀但仍未送出
- **下一步建议**：
  1. 改用 vtysh 在线配置（frr.conf 改为启动后 `vtysh -c 'configure terminal ...'`）
  2. 或换 cEOS/SR Linux 镜像（clab 官方 kind 支持更好，配置行为更可预测）
  3. 或验证 FRR 版本行为：检查 `show bgp neighbors` 的 SentOpen/Conflict 字段
- **状态**：不阻塞超最小演示核心验收（邻居 Established 已达成）；列为 Phase 1 收尾项