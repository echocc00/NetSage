"""评测题 root_causes 2→3 补齐（v0.5.0 波1 复审候选）。

为 106 道 troubleshoot（root_causes 恰好 2 条）补第 3 条真实互补根因：
- cause/probability/verify/fix 均按厂商惯例编写，避开各题已有 2 条
- probability 取低值（0.05~0.15），不与主因争 rank 1
- 文本锚点插入到 `expected_output:` 下 `  references:` 前 → diff 零污染

用法：python eval/runner/bump_root_causes.py  [--apply 写入 | 默认 dry-run 打印待处理]
"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATASET = ROOT / "eval" / "dataset"

# basename -> (cause, probability, verify, fix)
ADD3: dict[str, tuple[str, float, str, str]] = {
    # ============ BGP (27) ============
    "NSG-Q-0157.yaml": ("邻居 clear/重启后未收敛即被计数，瞬时超限触发 shutdown", 0.1,
        "show ip bgp neighbors 10.1.1.2 | include messages", "router bgp → bgp update-delay 后观察再重配"),
    "NSG-Q-0158.yaml": ("对端 iBGP 反射路径带出重复前缀，导致计数虚高", 0.1,
        "display bgp routing-table peer 10.1.1.2 | count prefix", "peer 去重 + 检查 RR 环路"),
    "NSG-Q-0159.yaml": ("重启窗口内既有前缀与新前缀叠加计数，超 teardown 阈值", 0.1,
        "show bgp neighbor 10.1.1.2 | match messages", "prefix-limit teardown 前先观察收敛"),
    "NSG-Q-0160.yaml": ("重新宣告全表触发瞬时计数超 max-routes", 0.1,
        "show ip bgp neighbors 10.1.1.2 | include max", "clear ip bgp 后按 session 收敛观察"),
    "NSG-Q-0161.yaml": ("下游客户重复宣告同一前缀导致撤回风暴（非抖动）", 0.1,
        "display bgp routing-table flap-info | include repeat", "peer 会话 reset + 抑制重复宣告"),
    "NSG-Q-0162.yaml": ("peer 会话频繁重连使 flap 计数未清零即触发抑制", 0.1,
        "show ip bgp dampening flap-statistics", "对 flap 源先抑制再统一调参"),
    "NSG-Q-0180.yaml": ("IPv6 地址族未激活，fe80 邻居不进入 Established", 0.05,
        "display bgp ipv6 peer | include active", "peer 2001:db8::2 activate"),
    "NSG-Q-0186.yaml": ("neighbor 未配 ipv6 activate 仅在 family 内宣告", 0.05,
        "show ip bgp ipv6 unicast summary", "address-family ipv6 unicast → activate"),
    "NSG-Q-0187.yaml": ("update-source 未指定使 TCP 源地址不被对端允许", 0.1,
        "show ip bgp neighbor 2001:db8::2 | include update-source", "neighbor update-source"),
    "NSG-Q-0199.yaml": ("ipv6 unicast 未 activate 导致 RT 无法交换", 0.1,
        "show bgp ipv6 unicast summary", "activate + 重发 route-map"),
    "NSG-Q-0207.yaml": ("client-to-client 反射未使能导致 RR 不同步", 0.1,
        "show bgp neighbor | include client", "bgp client-to-client reflection 开启"),
    "NSG-Q-0413.yaml": ("对端仍按旧 confed sub-as 宣告，路径不可识别", 0.1,
        "display bgp routing-table | include confed", "两端统一 confederation 配置"),
    "NSG-Q-0414.yaml": ("confed 邻居未 enable 地址族", 0.1,
        "show bgp summary | include confed", "address-family 内 enable peer"),
    "NSG-Q-0415.yaml": ("peer 未 enable 到对端地址族", 0.1,
        "display bgp peer | include enable", "address-family 内 peer enable"),
    "NSG-Q-0416.yaml": ("抑制后 reuse 时间过长导致路由长时间不恢复", 0.1,
        "show ip bgp dampening parameters", "bgp dampening 15 1500 2000 60"),
    "NSG-Q-0419.yaml": ("对端在 AS-Path 重复段被丢弃而非放行", 0.1,
        "display bgp routing-table | include as-path", "peer allow-as-in 数量校准"),
    "NSG-Q-0421.yaml": ("local-as 未配 no-prepend，路径带本端 AS 被对端拒收", 0.1,
        "show ip bgp summary | include local-as", "local-as 65002 no-prepend"),
    "NSG-Q-0422.yaml": ("RR 客户端地址族未 activate", 0.05,
        "display bgp peer | include activate", "address-family ipv4 → peer activate"),
    "NSG-Q-0423.yaml": ("ORIGINATOR_ID 相同使 RR 丢弃反射路径", 0.1,
        "show route protocol bgp | match originator", "逐跳改 router-id"),
    "NSG-Q-0434.yaml": ("VPNv4 地址族 peer 未 enable 导致 RT 不交换", 0.1,
        "display bgp vpnv4 peer", "vpnv4-family peer enable"),
    "NSG-Q-0438.yaml": ("客户侧误用 default 收 full table", 0.1,
        "display bgp routing-table statistics", "peer 仅宣告所需前缀"),
    "NSG-Q-0440.yaml": ("对端旧版本不识别 RFC 9234 错误处理字段", 0.1,
        "show bgp neighbors 10.1.1.2 | include version", "升级对端 BGP"),
    "NSG-Q-0441.yaml": ("IPv6 unicast 未启用导致通告被拒", 0.1,
        "display bgp ipv6 | include unicast", "bgp ipv6 unicast 开启"),
    "NSG-Q-0444.yaml": ("对端未启用 large-community 能力，属性被剥离", 0.1,
        "display bgp peer verbose | include large", "两端 advertise-large-community"),
    "NSG-Q-0446.yaml": ("ADD-PATH 未针对该邻居开启发送/接收方向", 0.1,
        "show ip bgp neighbors 10.1.1.2 | include add-path", "neighbor send/receive add-path 全开"),
    "NSG-Q-0451.yaml": ("FlowSpec 未 route-target 通告到 RR", 0.1,
        "display bgp ipv4 flowspec routing-table", "flowspec 地址族配 RT"),
    "NSG-Q-0461.yaml": ("ORR 位置策略未绑定到该 group", 0.1,
        "show bgp neighbor | include orr", "group 绑定 orr policy"),
    # ============ OSPF (27) ============
    "NSG-Q-0163.yaml": ("type-3 前缀本身频繁变，非物理层", 0.1,
        "show ospf database | match 0.0.0.0", "stub 区域内路由稳定后再调 throttle"),
    "NSG-Q-0165.yaml": ("DBD 报文 MTU 超对端接口 MTU", 0.1,
        "show ip ospf interface | include MTU", "两端接口 MTU 对齐"),
    "NSG-Q-0166.yaml": ("hello/dead 计时器不一致导致 2-way 后停滞", 0.1,
        "display ospf peer | include timer", "ospf timer hello 10 dead 40 对齐"),
    "NSG-Q-0167.yaml": ("接口认证缺失使对端忽略 hello", 0.1,
        "show ospf interface ge-0/0/0 | include authentication", "两端认证对齐"),
    "NSG-Q-0168.yaml": ("type-2 泛洪因 DR 切换频繁刷新", 0.1,
        "show ip ospf interface | include DR", "固定 DR priority"),
    "NSG-Q-0169.yaml": ("接口 area 挂错实例（ospfv3 1 area 0）", 0.05,
        "display ospfv3 interface 10GE1/0/1", "ospfv3 1 area 0 instance 18"),
    "NSG-Q-0170.yaml": ("dead-interval 也须一致（不取 4×hello 自动）", 0.1,
        "show ipv6 ospf interface | include Dead", "ipv6 ospf dead-interval 40"),
    "NSG-Q-0171.yaml": ("ABR 上 cost 设 max 抑制 type-3 通告", 0.1,
        "display ospf lsdb | include metric", "调整 summary cost"),
    "NSG-Q-0172.yaml": ("下游接口没宣告进该 area 导致 intra 缺失", 0.1,
        "show ip ospf interface brief", "network 语句补入"),
    "NSG-Q-0173.yaml": ("cost 计算把备路径判成等价/更优", 0.1,
        "show route protocol ospf", "设 reference-bandwidth 统一"),
    "NSG-Q-0174.yaml": ("stub 区域不允许 type-5 默认路由", 0.1,
        "show ip ospf database external", "改 totally-stub + 默认 cost"),
    "NSG-Q-0175.yaml": ("hello 认证类型不一致（区域 vs 接口）", 0.1,
        "display ospf interface | include Auth", "区域认证下沉到接口一致"),
    "NSG-Q-0176.yaml": ("VTEP 源接口未配 nve source-interface", 0.1,
        "display nve interface", "nve source-interface Loopback0"),
    "NSG-Q-0177.yaml": ("nve peer-vtep 缺对端导致 head-end 不发", 0.1,
        "show nve peers | include 10.0.0.2", "member vni + peer-vtep 补齐"),
    "NSG-Q-0178.yaml": ("NVE 接口对应 VNI 未加入 bridge-domain", 0.1,
        "display vxlan vni", "bridge-domain 绑定 vxlan"),
    "NSG-Q-0179.yaml": ("anycast-gateway 虚拟 MAC 与对端不同", 0.1,
        "show evpn mac-table | include 0200.0000", "两端 anycast MAC 一致"),
    "NSG-Q-0197.yaml": ("VTEP 源地址被前缀过滤", 0.1,
        "display ip routing-table 10.0.0.1", "IGP 放行 VTEP loopback"),
    "NSG-Q-0198.yaml": ("NSSA 转 type-5 的 ABR 漏 always-translate", 0.1,
        "show ospf database nssa-external", "set area 0 nssa 转译开"),
    "NSG-Q-0204.yaml": ("等价路径来自不同区域导致 ECMP 不成立", 0.1,
        "show ip route 10.0.0.0 | include equal", "same area 内 ECMP"),
    "NSG-Q-0211.yaml": ("BFD 状态未联动 OSPF（bfd 配而未 enable）", 0.1,
        "show ip ospf | include bfd", "ip ospf bfd 开启"),
    "NSG-Q-0212.yaml": ("对端未 import 本端 type-1", 0.1,
        "display ospfv3 lsdb | include ASBR", "对端 import 补上"),
    "NSG-Q-0417.yaml": ("接口 preempt 使 DR 反复抢占", 0.1,
        "show ospf neighbor | match DR", "禁抢占或固定 priority"),
    "NSG-Q-0418.yaml": ("stub 区域未含 ASBR 的 type-4 需人工注入", 0.05,
        "show ip ospf database | include Type-4", "ABR 配 area range 覆盖 ASBR 环回"),
    "NSG-Q-0420.yaml": ("OSPF process 间重发布导致路由环", 0.1,
        "display ospf routing | include redist", "检查重发布方向"),
    "NSG-Q-0424.yaml": ("接口网络类型 p2mp 与对端不匹配", 0.1,
        "show ipv6 ospf interface | include Network", "统一 network-type p2p"),
    "NSG-Q-0425.yaml": ("进程号不一致（不同 ospfv3 实例）", 0.1,
        "display ospfv3 | include process", "统一进程号"),
    "NSG-Q-0426.yaml": ("对端参考带宽不同使 cost 失衡", 0.1,
        "show ipv6 ospf | include reference", "两端 reference-bandwidth 一致"),
    "NSG-Q-0433.yaml": ("区域认证类型（md5 vs 明文）不一致", 0.1,
        "display ospf | include authentication", "统一认证类型"),
    "NSG-Q-0436.yaml": ("接口实例号不符使邻居隔离", 0.1,
        "display ospfv3 interface | include instance", "两端 instance 一致"),
    "NSG-Q-0439.yaml": ("NSSA ABR 未转译 type-7→type-5", 0.1,
        "display ospfv3 lsdb | include type-5", "always-translate 开启"),
    "NSG-Q-0442.yaml": ("接口 mt 未匹配使 LSA 被拒", 0.1,
        "show ip ospf interface | include MTU", "接口 MTU 对齐"),
    "NSG-Q-0445.yaml": ("GR helper 端 require-lsa 设置挡住恢复", 0.1,
        "display ospf graceful-restart | include require", "关 require-lsa 或补 LSA"),
    # ============ VXLAN/EVPN (14) ============
    "NSG-Q-0202.yaml": ("Type-5 需 ip-prefix 导入才通告", 0.1,
        "display evpn route type-5", "address-family l2vpn evpn → 配 ip 导入"),
    "NSG-Q-0427.yaml": ("BUM 需 ingress-replication 协议一致", 0.1,
        "show vxlan vni | include ingress", "两端 ingress-replication protocol bgp"),
    "NSG-Q-0428.yaml": ("RR 上 member vni 未含目标 VNI", 0.1,
        "show bgp l2vpn evpn | include member", "member vni 补齐"),
    "NSG-Q-0429.yaml": ("源接口被 ACL 过滤使 VTEP 通信失败", 0.1,
        "display ip routing-table | include 10.0.0.1", "放行 VTEP 源 ACL"),
    "NSG-Q-0430.yaml": ("VBDif 缺 arp collect host 使远端 MAC 不学", 0.1,
        "display vxlan arp | include collect", "arp collect host 补配"),
    "NSG-Q-0435.yaml": ("Type-3 需 RT 匹配才能互通", 0.1,
        "show bgp l2vpn evpn | include RT", "两端 EVPN RT 一致"),
    "NSG-Q-0437.yaml": ("Symmetric IRB 缺网关 VNI 互通", 0.1,
        "show evpn instance | include L3", "配 L3 VNI + 网关"),
    "NSG-Q-0459.yaml": ("ESI 多归属需 DF 一致否则 BUM 重复", 0.1,
        "display evpn esi df", "统一 DF election"),
    "NSG-Q-0460.yaml": ("MAC 重复因 arp suppression 未同步到新 leaf", 0.1,
        "show l2vpn evpn arp | include suppress", "新 leaf 补 arp suppress"),
    # ============ MPLS/VRRP/HSRP/QinQ/STP/LACP/DHCP/AAA/802.1X/IPsec/ISIS/Multicast/其余 ============
    "NSG-Q-0181.yaml": ("LDP 传输地址未配，用接口地址建邻失败", 0.1,
        "show mpls ldp discovery | include transport", "mpls ldp router-id 指定"),
    "NSG-Q-0182.yaml": ("RSVP 未 enable 到目标 LSP", 0.1,
        "show rsvp neighbor", "protocols rsvp interface 全开"),
    "NSG-Q-0183.yaml": ("VRRP priority 未区分主备（同 100）", 0.1,
        "display vrrp verbose | include priority", "主 120 / 备 100"),
    "NSG-Q-0184.yaml": ("VRRP 认证 key 不一致导致互斥", 0.1,
        "show vrrp detail | include auth", "统一认证"),
    "NSG-Q-0185.yaml": ("HSRP 组号/虚拟 IP 不一致", 0.1,
        "show hsrp brief | include group", "两端同组同 VIP"),
    "NSG-Q-0188.yaml": ("IKE 生命周期/加密套件不一致", 0.1,
        "show crypto isakmp sa", "isakmp policy 统一"),
    "NSG-Q-0189.yaml": ("IKEv2 认证方法一端 EAP 一端证书", 0.1,
        "display ikev2 policy", "两端认证方法一致"),
    "NSG-Q-0190.yaml": ("QinQ 仅单层 tag 转发导致不匹配", 0.1,
        "display vlan translation", "双层 tag 端口正确封装"),
    "NSG-Q-0191.yaml": ("ND RA 未周期性发送使邻居老化", 0.1,
        "display ipv6 nd ra", "ipv6 nd ra interval 检查"),
    "NSG-Q-0192.yaml": ("DHCP 中继未开启使请求到不了 snooping", 0.1,
        "show ip dhcp snooping | include relay", "ip dhcp relay 开启"),
    "NSG-Q-0193.yaml": ("AAA 方法列表未引用 RADIUS", 0.1,
        "show aaa servers | include method", "aaa authentication 引用 radius"),
    "NSG-Q-0194.yaml": ("RADIUS 端口/密钥不符", 0.1,
        "display radius configuration", "radius-server key 对齐"),
    "NSG-Q-0195.yaml": ("成员口模式不一致（active/passive）", 0.1,
        "show etherchannel summary | include mode", "两端成员口模式一致"),
    "NSG-Q-0196.yaml": ("MST 实例到 VLAN 映射不一致", 0.1,
        "show spanning-tree mst | include vlan", "instance vlan 映射统一"),
    "NSG-Q-0200.yaml": ("IS-IS LSP 长度/overload 未处理", 0.1,
        "display isis lsp | include overload", "set-overload 排查"),
    "NSG-Q-0201.yaml": ("PVST 未收敛到根（根桥漂移）", 0.1,
        "show spanning-tree vlan 10 | include root", "root primary 固定"),
    "NSG-Q-0203.yaml": ("HRP 心跳超时使状态误判", 0.1,
        "display hrp state", "hrp 心跳间隔调优"),
    "NSG-Q-0205.yaml": ("RA 被静态默认路由抑制", 0.05,
        "display ipv6 nd ra | include default", "删除冲突默认路由"),
    "NSG-Q-0206.yaml": ("ACL 未配 remark 使运维难维护（非功能性）", 0.05,
        "show ip access-list | include remark", "补 remark 便于审查"),
    "NSG-Q-0208.yaml": ("metric-style 一端 narrow 一端 wide 单向不优", 0.1,
        "display isis | include metric-style", "两端统一 wide"),
    "NSG-Q-0209.yaml": ("relay 端 interface 缺 ip helper 仅单方向", 0.1,
        "show running-config interface vlan10", "入/出 helper-address 都配"),
    "NSG-Q-0210.yaml": ("RA 未发（advertise 未开）", 0.1,
        "show ipv6 router-advertisement | include advertise", "advertise 开启"),
    "NSG-Q-0431.yaml": ("ESP 封装导致分片被中间丢弃", 0.1,
        "show crypto ipsec sa | include frag", "DF 位调整 + MSS"),
    "NSG-Q-0432.yaml": ("IPsec 封装模式（tunnel vs transport）不一致", 0.1,
        "display ipsec sa | include mode", "两端封装模式统一"),
    "NSG-Q-0443.yaml": ("RA 中 M/O flag 被网关策略覆盖", 0.05,
        "show ipv6 interface | include Managed", "与 DHCPv6 协调"),
    "NSG-Q-0447.yaml": ("IGMP 版本不一致（v2 vs v3）", 0.1,
        "display igmp | include version", "统一 IGMP 版本"),
    "NSG-Q-0448.yaml": ("上游 PIM 邻居 RPF 接口选择错", 0.1,
        "show ip mroute | include RP", "静态 RP + 正确 RPF"),
    "NSG-Q-0449.yaml": ("MSDP 需配置 SA 缓存一致", 0.1,
        "display msdp sa-cache", "缓存策略统一"),
    "NSG-Q-0450.yaml": ("MSDP peer 需双向建连才转发 SA", 0.1,
        "show ip msdp peer | include up", "双向 msdp peer"),
    "NSG-Q-0452.yaml": ("MACsec 需统一 cipher suite", 0.1,
        "display macsec | include cipher", "两端 cipher 一致"),
    "NSG-Q-0453.yaml": ("MKA 需同一 key server 优先级", 0.05,
        "show mka sessions | include key-server", "priority 高者固定"),
    "NSG-Q-0454.yaml": ("gRPC 端口被防火墙拦", 0.1,
        "show telemetry | include port", "放行 50051"),
    "NSG-Q-0455.yaml": ("gNMI 端口/订阅粒度不匹配", 0.1,
        "display telemetry | include port", "订阅口径统一"),
    "NSG-Q-0456.yaml": ("回滚点未包含全部变更段", 0.1,
        "display rollback | include point", "回滚点含完整片段"),
    "NSG-Q-0457.yaml": ("RADIUS 认证/计费端口分离错", 0.1,
        "show aaa | include radius", "auth/accounting 端口一致"),
    "NSG-Q-0458.yaml": ("TACACS+ 需单连接模式避免乱序", 0.1,
        "display tacacs | include single", "single-connection 开启"),
    "NSG-Q-0462.yaml": ("VRRP track 目标被误删", 0.1,
        "display vrrp verbose | include track", "track 目标还原"),
    "NSG-Q-0463.yaml": ("采样方向（入/出）配错", 0.1,
        "display netstream | include direction", "sampler 绑定正确方向"),
}


def anchor_insert(lines: list[str], block: list[str]) -> list[str]:
    """在 `expected_output:` 的 `  references:` 前插入 root_causes 子项块。"""
    for i, l in enumerate(lines):
        if l.rstrip() == "  references:":
            return lines[:i] + block + lines[i:]
    raise ValueError("未找到 references 锚点")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    pending, ok, fail = [], 0, []
    for f in sorted(DATASET.glob("NSG-Q-*.yaml")):
        if f.name not in ADD3:
            continue
        lines = f.read_text(encoding="utf-8").splitlines()
        cause = ADD3[f.name][0]
        if any(cause in l for l in lines):
            fail.append(f"{f.name}: 第3条与已有内容重复")
            continue
        block = [
            "  - rank: 3",
            f"    cause: {cause}",
            f"    probability: {ADD3[f.name][1]}",
            f"    verify: {ADD3[f.name][2]}",
            f"    fix: {ADD3[f.name][3]}",
            "",
        ]
        out = anchor_insert(lines, block)
        if args.apply:
            f.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
            ok += 1
        else:
            pending.append(f.name)
    if args.apply:
        print(f"已写入 {ok} 个文件；失败 {len(fail)}")
        for e in fail:
            print("  ✗", e)
    else:
        print(f"dry-run: 待补 {len(pending)} 题（--apply 生效）；重复冲突 {len(fail)}")
        for e in fail:
            print("  ✗", e)


if __name__ == "__main__":
    main()
