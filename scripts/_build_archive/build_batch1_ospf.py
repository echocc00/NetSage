"""BGP 后 5 道 + OSPF 5 道 + 接口/路由 5 道。"""
import yaml, os

OUT = 'eval/dataset'

def save(q):
    p = f'{OUT}/{q["id"]}.yaml'
    yaml.dump(q, open(p, 'w', encoding='utf-8'),
              default_flow_style=False, allow_unicode=True, sort_keys=False, width=240)
    print(f'  wrote {q["id"]}')

# Q-0039 BGP Capability (Cisco IPv6)
save({
    'id': 'NSG-Q-0039', 'title': 'BGP IPv6 邻居卡 OpenConfirm（思科 IOS-XE 17，地址族未独立 activate）',
    'category': 'troubleshoot', 'vendor': 'cisco', 'version': 'IOS-XE-17.09', 'difficulty': 3,
    'tags': ['bgp', 'capability', 'address-family', 'ipv6', 'mp-bgp'],
    'input': {
        'symptom': 'IPv6 BGP peer 1999::2 卡 OpenConfirm；IPv4 邻居正常',
        'device_info': {'model': 'ASR 1001-X', 'version': 'IOS-XE 17.09.04a'},
        'evidence': [
            {'config_snippet': 'router bgp 65001\n  neighbor 1999::2 remote-as 65002\n  address-family ipv4 unicast\n   neighbor 1999::2 activate\n  ! ⚠️ 缺 address-family ipv6 unicast'},
            {'log_lines': ['%BGP-5-ADJCHANGE: neighbor 1999::2 Up', 'OpenConfirm: "no matching interface-protocol"']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'IPv6 地址族未独立 activate（v4 family 内 activate 对 IPv6 邻居无效）', 'probability': 0.85,
             'evidence': ['"no matching interface-protocol"', 'OpenConfirm 卡住'],
             'verify': 'show ip bgp neighbors 1999::2 | include AFI / IPv6',
             'fix': 'router bgp 65001\n  address-family ipv6 unicast\n   neighbor 1999::2 activate\n  exit-address-family',
             'rollback': 'address-family ipv6 unicast → no neighbor 1999::2 activate'},
            {'rank': 2, 'cause': 'MP-BGP capability 协商问题', 'probability': 0.1,
             'verify': 'show ip bgp neighbors 1999::2 | include capability',
             'fix': '重新 add capability'},
            {'rank': 3, 'cause': 'IPv6 链路不通', 'probability': 0.05,
             'verify': 'show ipv6 route 1999::2',
             'fix': '互联接口配 IPv6 + enable ipv6 routing'},
        ],
        'references': [{'type': 'rfc', 'url': 'https://datatracker.ietf.org/doc/html/rfc2545', 'title': 'BGP-4 MP for IPv6'}],
    },
    'anti_examples': ['请重启', '改成 IPv4', '关闭 IPv6'],
    'grading_rubric': {
        'must_have': ['address-family ipv6 unicast activate', '≥1 验证命令'],
        'nice_to_have': ['RFC 2545 引用'],
        'penalty': ['重启'],
    },
})

# Q-0040 BGP Maximum-Prefix (Huawei)
save({
    'id': 'NSG-Q-0040', 'title': 'BGP maximum-prefix 超限（华为 VRP-8.180，对端路由泄漏）',
    'category': 'troubleshoot', 'vendor': 'huawei', 'version': 'VRP-8.180', 'difficulty': 3,
    'tags': ['bgp', 'maximum-prefix', 'route-leak', 'shutdown'],
    'input': {
        'symptom': 'BGP 邻居被强制 Idle: %BGP-3-MAXPFX_EXCEEDED',
        'device_info': {'model': 'NE40E-X8A', 'version': 'VRP-8.180'},
        'evidence': [
            {'config_snippet': 'bgp 65001\n  peer 10.1.1.2 as-number 65002\n  peer 10.1.1.2 maximum-prefix 1000 80 restart 30\n# 对端发了 5000 前缀'},
            {'log_lines': ['%BGP-3-MAXPFX_EXCEEDED: Peer 10.1.1.2 exceeded maximum-prefix limit 1000', 'Peer 10.1.1.2 -> Idle']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': '对端 BGP 路由泄漏（攻击/配置错）导致前缀超限', 'probability': 0.7,
             'evidence': ['MAXPFX_EXCEEDED', '对端发了 5000 前缀（远超 1000 上限）'],
             'verify': 'display bgp peer 10.1.1.2 verbose | include prefix',
             'fix': 'bgp 65001\n  # 方案 A：上限放宽到 10000\n  peer 10.1.1.2 maximum-prefix 10000 90\n  # 方案 B：配合 prefix-list 限制\n  ip ip-prefix NET-LIMIT index 10 deny 10.0.0.0 8 greater-equal 17\n  peer 10.1.1.2 ip-prefix NET-LIMIT import',
             'rollback': 'undo peer 10.1.1.2 maximum-prefix'},
            {'rank': 2, 'cause': 'maximum-prefix threshold 配置太严，restarter 时间未到', 'probability': 0.2,
             'verify': 'display bgp peer 10.1.1.2 | include restart',
             'fix': '重启前手动 reset: reset bgp 10.1.1.2'},
            {'rank': 3, 'cause': '上游 65002 扩容新业务路由', 'probability': 0.1,
             'verify': '与上游 65002 沟通',
             'fix': '协商 prefix 上限'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://support.huawei.com/vrp-bgp-maximum-prefix', 'version': 'VRP-8.180'}],
    },
    'anti_examples': ['请重启', '不限 prefix 数', '删除 BGP 邻居'],
    'grading_rubric': {
        'must_have': ['诊断路由泄漏', '配置 prefix-list + maximum-prefix 调整'],
        'nice_to_have': ['reset bgp'],
        'penalty': ['重启'],
    },
})

# Q-0041 BGP route-leak via community
save({
    'id': 'NSG-Q-0041', 'title': 'BGP 路由泄漏（Juniper 21.2，community 不当导致路由跨 VRF 流）',
    'category': 'troubleshoot', 'vendor': 'juniper', 'version': '21.2R1', 'difficulty': 4,
    'tags': ['bgp', 'route-leak', 'community', 'rt'],
    'input': {
        'symptom': 'VRF-A 中的 192.168.0.0/24 路由泄漏到 VRF-B（不应跨租户）',
        'device_info': {'model': 'MX204', 'version': 'Junos 21.2R1.6'},
        'evidence': [
            {'config_snippet': 'set routing-instances VRF-A instance-type vrf\nset routing-instances VRF-A route-distinguisher 65000:1\nset routing-instances VRF-A vrf-target target:65000:100\n# ⚠️ 漏加 export 限定，导致所有 VRF 共享 RT\n'},
            {'log_lines': ['show route 192.168.0.0/24 table VRF-B.inet.0: 通过 (security warning)']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'VRF target 范围过大（共享 RT 触发跨 VRF 路由通告）', 'probability': 0.6,
             'evidence': ['show route table VRF-B 看到 VRF-A 的路由', 'vrf-target 配置未限定 import'],
             'verify': 'show routing-instances VRF-A vrf-target\nshow route table VRF-B.inet.0 hidden',
             'fix': 'set routing-instances VRF-A vrf-target export target:65000:101 import target:65000:101\n# 限制 RT 范围为 101（与 VRF-A 内部一致）',
             'rollback': 'rollback 1'},
            {'rank': 2, 'cause': 'rib-group 全局共享', 'probability': 0.3,
             'verify': 'show rib-groups',
             'fix': '为每个 VRF 独立 rib-group'},
            {'rank': 3, 'cause': 'policy import 误用 import vrf-match', 'probability': 0.1,
             'verify': 'show policy',
             'fix': 'policy-statement 严格限定 target'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://www.juniper.net/documentation/junos-21.2/vrf-target', 'version': '21.2R1'}],
    },
    'anti_examples': ['请重启', '重启 routing process', '全开 target'],
    'grading_rubric': {
        'must_have': ['诊断 VRF-Target 误共享', '修复：限定 RT'],
        'nice_to_have': ['policy import 检查'],
        'penalty': ['重启'],
    },
})

# Q-0042 BGP eBGP/iBGP 混淆 (H3C)
save({
    'id': 'NSG-Q-0042', 'title': 'eBGP/iBGP 邻居混淆（华三 Comware 7，next-hop-self 缺失）',
    'category': 'troubleshoot', 'vendor': 'h3c', 'version': 'Comware-7.1.070', 'difficulty': 3,
    'tags': ['bgp', 'ibgp', 'ebgp', 'next-hop-self'],
    'input': {
        'symptom': 'iBGP 同 AS 内部邻居可达，但内部 RR 反射给 iBGP 客户端的路由 next-hop 不可达（黑洞）',
        'device_info': {'model': 'S9850-32B', 'version': 'Comware 7.1.070 R7625'},
        'evidence': [
            {'config_snippet': 'bgp 65000\n  peer 10.0.0.1 as-number 65000\n  peer 10.0.0.1 reflect-client\n  ! ⚠️ RR 上未加 peer x.x.x.x next-hop-local'},
            {'log_lines': ['display bgp routing-table 192.168.0.0/24: next-hop 10.1.1.2', '但 show ip route 10.1.1.2: unreachable']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'RR 上缺 next-hop-local，导致 iBGP 客户端无法 resolve next-hop', 'probability': 0.7,
             'evidence': ['路由有 next-hop 10.1.1.2 但 IGP 无路径'],
             'verify': 'display bgp routing-table 192.168.0.0/24 / display ip routing-table',
             'fix': 'bgp 65000\n  peer 10.0.0.1 next-hop-local\n  peer 10.0.0.1 reflect-client',
             'rollback': 'undo peer 10.0.0.1 next-hop-local'},
            {'rank': 2, 'cause': 'iBGP 客户端 RR 之间做 full-mesh 而非 RR 模式', 'probability': 0.2,
             'verify': 'display bgp peer | include reflect',
             'fix': '确定 RR 层级'},
            {'rank': 3, 'cause': 'cluster-id 冲突', 'probability': 0.1,
             'verify': 'display bgp cluster',
             'fix': 'bgp 65000 → cluster-id 10.0.0.1'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://www.h3c.com/cn/d_202206/bgp-rr-next-hop', 'version': 'Comware 7.1.070'}],
    },
    'anti_examples': ['请重启', '删 RR 重配', 'close BGP peer'],
    'grading_rubric': {
        'must_have': ['next-hop-local', '诊断 RR vs iBGP'],
        'nice_to_have': ['cluster-id'],
        'penalty': ['重启'],
    },
})

# Q-0043 BGP EVPN Type-2 (Cisco NX-OS)
save({
    'id': 'NSG-Q-0043', 'title': 'BGP EVPN Type-2 路由泄漏（思科 NX-OS 9.3，route-target import 错配）',
    'category': 'troubleshoot', 'vendor': 'cisco', 'version': 'NX-OS-9.3', 'difficulty': 4,
    'tags': ['bgp', 'evpn', 'type-2', 'route-target'],
    'input': {
        'symptom': 'Leaf-A 上学习不到 Leaf-B 通告的 VM1 MAC 地址（Type-2 路由）',
        'device_info': {'model': 'Nexus 9336C-FX2', 'version': 'NX-OS 9.3(8)'},
        'evidence': [
            {'config_snippet': '# Leaf-B (vni 10010)\nl2vpn evpn instance 10 point-to-point\n  rd 10.0.0.2:10\n  route-target import 65000:10010\n  route-target export 65000:10000   # ⚠️ 与 import 不一致'},
            {'log_lines': ['show bgp l2vpn evpn route-type 2: Leaf-B 导出 RT=65000:10000', 'show bgp l2vpn evpn route-type 2 received on Leaf-A: 无']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'Leaf-B 导出 RT 配错（65000:10000 vs 应有 65000:10010）', 'probability': 0.75,
             'evidence': ['Leaf-B export RT=65000:10000, Leaf-A import RT=65000:10010 不匹配'],
             'verify': 'show bgp l2vpn evpn\nshow bgp l2vpn evpn route-type 2',
             'fix': 'conf t\n  l2vpn evpn instance 10 point-to-point\n   route-target export 65000:10010\n  end',
             'rollback': 'route-target export 65000:10000'},
            {'rank': 2, 'cause': 'RD 配置格式错误', 'probability': 0.1,
             'verify': 'show l2vpn evpn summary',
             'fix': 'RD 格式 ip:nn (如 10.0.0.1:10)'},
            {'rank': 3, 'cause': 'NVE peer BGP 邻居未建立', 'probability': 0.1,
             'verify': 'show nve peers',
             'fix': 'bgp peer 邻居修复'},
            {'rank': 4, 'cause': 'BUM 抑制 ARP suppression 全网不一致', 'probability': 0.05,
             'verify': 'show ip arp suppression-cache',
             'fix': '统一起配置'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://www.cisco.com/c/en/us/td/docs/switches/datacenter/sw/nx-os/nxcli/vxlan', 'version': 'NX-OS-9.3'}],
    },
    'anti_examples': ['请重启', '删除 l2vpn evpn instance 重建', '改 VNI/VTEP'],
    'grading_rubric': {
        'must_have': ['诊断 export RT 错配', '修复 export 与 import 一致'],
        'nice_to_have': ['解释 EVPN RT 在 NLRI 中的角色'],
        'penalty': ['重启'],
    },
})

print("===" * 20)
print("OSPF 系列（5 题）")
print("===" * 20)

# Q-0044 OSPF 卡 Exstart Cisco
save({
    'id': 'NSG-Q-0044', 'title': 'OSPF 卡 EXSTART（思科 IOS-XE 17，MTU 一致但是 DR 优先级错配）',
    'category': 'troubleshoot', 'vendor': 'cisco', 'version': 'IOS-XE-17.09', 'difficulty': 3,
    'tags': ['ospf', 'exstart', 'dr-priority', 'mtu'],
    'input': {
        'symptom': 'OSPF 卡 EXSTART 反复重试',
        'device_info': {'model': 'Catalyst 9300-48P', 'version': 'IOS-XE 17.09.04a', 'interfaces': ['GigabitEthernet1/0/24']},
        'evidence': [
            {'config_snippet': 'interface GigabitEthernet1/0/24\n ip address 10.1.1.1 255.255.255.252\n ip ospf 1 area 0\n ip ospf priority 200\nip mtu 1500\n\n! 对端\ninterface GigabitEthernet1/0/24\n ip ospf priority 0   # ⚠️ 0 = 不参与 DR 选举，永远 DROther'},
            {'log_lines': ['%OSPF-5-ADJCHG: Neighbor 10.0.0.2 Down, AdjInit 失败', 'show ip ospf neighbor: state EXSTART 反复']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'OSPF priority 0 在 BROADCAST 链路下永远不能成为 DR，导致 DR 选举失败', 'probability': 0.5,
             'evidence': ['OSPF BROADCAST 类型需要 DR/BDR，priority 0 表示不参与选举', 'AdjInit 失败对端没有 candidate DR'],
             'verify': 'show ip ospf interface g1/0/24 | include "Priority"\nshow ip ospf neighbor | include DR',
             'fix': 'interface g1/0/24\n  no ip ospf priority 0\n  ip ospf priority 200',
             'rollback': 'ip ospf priority 0'},
            {'rank': 2, 'cause': 'MTU mismatch（OSPF 卡 EXSTART 经典原因）', 'probability': 0.3,
             'verify': 'show interface g1/0/24 | include MTU\nshow ip ospf interface',
             'fix': '两侧 ip mtu 1500 对齐'},
            {'rank': 3, 'cause': '子网掩码不一致（OSPF 要求同一 subnet）', 'probability': 0.1,
             'verify': 'show ip interface brief',
             'fix': '对齐子网掩码'},
            {'rank': 4, 'cause': 'OSPF 网络类型错配（broadcast vs p2p）', 'probability': 0.1,
             'verify': 'show ip ospf interface | include Network',
             'fix': '两侧 ip ospf network 类型对齐'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://www.cisco.com/c/en/us/support/ospf-exstart', 'version': 'IOS-XE-17.09'}],
    },
    'anti_examples': ['请重启', '删除 OSPF 进程', '把 priority 都设为 1'],
    'grading_rubric': {
        'must_have': ['诊断 priority 0 + MTU 双重原因', '修复'],
        'nice_to_have': ['explain BROADCAST vs P2P'],
        'penalty': ['重启'],
    },
})

# Q-0045 OSPF LSA Flooding (Huawei)
save({
    'id': 'NSG-Q-0045', 'title': 'OSPF LSDB 频繁刷新（华为 VRP-8.180，SPF 频繁计算导致 CPU 高）',
    'category': 'troubleshoot', 'vendor': 'huawei', 'version': 'VRP-8.180', 'difficulty': 4,
    'tags': ['ospf', 'lsa', 'spf', 'cpu'],
    'input': {
        'symptom': 'OSPF display ospf spf-statistics 1000 次/分钟，CPU 持续 >60%',
        'device_info': {'model': 'CE5880-C48S8CQ', 'version': 'VRP-8.180'},
        'evidence': [
            {'config_snippet': 'ospf 1\n  area 0.0.0.0\n    network 10.1.1.0 0.0.0.255\n# 邻居 50+ 个，且每 60s 都有 1 个邻居重启（链路上 SDH 跳变）'},
            {'log_lines': ['%OSPF/4/SHORTAGE_OF_LSBD(l): LSDB overflow attempts 5', 'display ospf cpu-usage: 65% (SPF 80%)']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': '邻居频繁重启触发 LSA 重新泛洪，SPF 频繁计算', 'probability': 0.7,
             'evidence': ['LSDB overflow 告警', 'SPF 频繁', '设备邻居 50+ 个'],
             'verify': 'display ospf spf-statistics\ndisplay ospf peer | include "Up| Established" | head',
             'fix': '# 方案 A：调小 SPF throttle\nospf 1\n  spf-schedule-interval 5000 10000 20000\n  initial-delay 1000\n# 方案 B：触发型 LSA 接口上配 ospf timer hello 30 dead 120 降低 churn',
             'rollback': 'undo spf-schedule-interval'},
            {'rank': 2, 'cause': 'LSA 老化触发频繁重生成', 'probability': 0.2,
             'verify': 'display ospf lsdb | include LSAge',
             'fix': '调大 LSA refresh 间隔'},
            {'rank': 3, 'cause': '路由震荡（上游 IGP router flap）', 'probability': 0.1,
             'verify': 'display logbuffer | include "Neighbor up"',
             'fix': '上游稳定性治理'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://support.huawei.com/vrp-ospf-spf-throttle', 'version': 'VRP-8.180'}],
    },
    'anti_examples': ['请重启', '删除 OSPF 重配', '关闭 SPF'],
    'grading_rubric': {
        'must_have': ['诊断 SPF 频繁计算', 'spf-schedule-interval 调优'],
        'nice_to_have': ['initial-delay 解释'],
        'penalty': ['重启'],
    },
})

# Q-0046 OSPF Init/2-way (H3C)
save({
    'id': 'NSG-Q-0046', 'title': 'OSPF 卡 Init 状态（华三 Comware 7，area ID 不一致 + 认证 MD5 错配）',
    'category': 'troubleshoot', 'vendor': 'h3c', 'version': 'Comware-7.1.070', 'difficulty': 3,
    'tags': ['ospf', 'init', 'area-id', 'md5'],
    'input': {
        'symptom': 'OSPF 卡 Init，邻居不进入 EXSTART',
        'device_info': {'model': 'S9850-32B', 'version': 'Comware 7.1.070 R7625'},
        'evidence': [
            {'config_snippet': '# Spine\nospf 1 router-id 10.0.0.1\n  area 0.0.0.1    # area id 0.0.0.1\n  network 10.1.1.0 0.0.0.255\n# Leaf\nospf 1 router-id 10.0.0.2\n  area 0.0.0.2    # ⚠️ area id 0.0.0.2 不一致'},
            {'log_lines': ['%OSPF/3/NEIGHBOR_CHANGE(l): Neighbor 10.0.0.1 stayed in Init state']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': '两端 area-id 不一致（0.0.0.1 vs 0.0.0.2）', 'probability': 0.6,
             'evidence': ['Init 状态说明收到了 Hello 但其他字段不一致'],
             'verify': 'display ospf peer\ndisplay ospf brief',
             'fix': 'ospf 1\n  # Leaf 这边统一改 area 0.0.0.1\n  area 0.0.0.1\n  undo area 0.0.0.2',
             'rollback': 'undo area 0.0.0.1'},
            {'rank': 2, 'cause': 'OSPF 认证 MD5 不一致', 'probability': 0.25,
             'verify': 'display ospf interface | include Authentication',
             'fix': 'ospf authentication-mode md5 1 cipher Huawei@2024'},
            {'rank': 3, 'cause': 'Hello/Dead 计时器不一致（H3C 容忍差，但与认证错配易暴露）', 'probability': 0.15,
             'verify': 'display ospf interface | include Hello',
             'fix': 'ospf timer hello 10 dead 40'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://www.h3c.com/cn/d_202206/ospf-init', 'version': 'Comware 7.1.070'}],
    },
    'anti_examples': ['请重启', '改 area 0.0.0.0', '关闭认证'],
    'grading_rubric': {
        'must_have': ['诊断 area-id 不一致', '修复：统一 area'],
        'nice_to_have': ['认证检查'],
        'penalty': ['重启'],
    },
})

# Q-0047 OSPF NSSA ABR Type-7 (Arista)
save({
    'id': 'NSG-Q-0047', 'title': 'OSPF NSSA Type-7 不转 Type-5（Arista EOS 4.24，ABR 漏配 area nssa）',
    'category': 'troubleshoot', 'vendor': 'arista', 'version': '4.24', 'difficulty': 4,
    'tags': ['ospf', 'nssa', 'type-7', 'type-5', 'abr'],
    'input': {
        'symptom': 'NSSA 区外部路由注入后，其他 OSPF area 学不到（无 type-5 路由）',
        'device_info': {'model': 'DCS-7280QR-C36', 'version': 'EOS 4.24.6M'},
        'evidence': [
            {'config_snippet': '# ABR device\nrouter ospf 10\n  area 0.0.0.1 stub no-summary nssa  # ⚠️ stub 和 nssa 互斥'}
            ,
            {'log_lines': ['show ip ospf database: 本地 area 0.0.0.1 有 type-7', 'show ip ospf database summary: 0.0.0.0 area 没有 type-5']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'stub 与 nssa 互斥（二选一）', 'probability': 0.65,
             'evidence': ['NSSA 配置被 stub 覆盖', 'no type-5 路由生成'],
             'verify': 'show ip ospf area 0.0.0.1 detail\nshow running-config section ospf',
             'fix': 'router ospf 10\n  no area 0.0.0.1 stub\n  area 0.0.0.1 nssa',
             'rollback': 'area 0.0.0.1 stub'},
            {'rank': 2, 'cause': 'ABR 上 P-bit 标记为 0（不翻译 type-7→type-5）', 'probability': 0.2,
             'verify': 'show ip ospf database nssa-external | include P-bit',
             'fix': '在 NSSA ASBR 上配置 nssa 把 P-bit 设为 1（默认是 1）'},
            {'rank': 3, 'cause': 'ABR ABR-type 不是 ASBR，只转 type-3，不转 type-5', 'probability': 0.1,
             'verify': 'show ip ospf border-routers',
             'fix': '在 ABR 上加 always-translate-7-to-5'},
            {'rank': 4, 'cause': 'NSSA 区 filter-list 阻挡了 type-5', 'probability': 0.05,
             'verify': 'show ip ospf filter',
             'fix': '调整 filter-list'},
        ],
        'references': [{'type': 'rfc', 'url': 'https://datatracker.ietf.org/doc/html/rfc3101', 'title': 'The OSPF NSSA Option'}],
    },
    'anti_examples': ['请重启', '改 area 0', '关闭 NSSA'],
    'grading_rubric': {
        'must_have': ['诊断 stub/nssa 互斥', '修复：no stub + nssa'],
        'nice_to_have': ['P-bit 解释'],
        'penalty': ['重启'],
    },
})

# Q-0048 OSPF 路由缺失（Juniper）
save({
    'id': 'NSG-Q-0048', 'title': 'OSPF 路由表中某些 area 间路由缺失（Juniper 21.2，ABR type-3 漏配）',
    'category': 'troubleshoot', 'vendor': 'juniper', 'version': '21.2R1', 'difficulty': 4,
    'tags': ['ospf', 'abr', 'summary', 'type-3'],
    'input': {
        'symptom': 'show route 192.168.10.0/24: 缺失！期望从 area 0 通过 ABR 通告到 area 0.0.0.10',
        'device_info': {'model': 'MX204', 'version': 'Junos 21.2R1.6'},
        'evidence': [
            {'config_snippet': 'set protocols ospf area 0.0.0.0 interface ge-0/0/0\nset protocols ospf area 0.0.0.10 interface ge-0/0/1 stub no-summaries\n# ⚠️ stub no-summaries 不收 type-3 路由'},
            {'log_lines': ['show route 192.168.10.0/24: not in routing table']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'stub no-summaries 抑制 type-3 summary 路由', 'probability': 0.85,
             'evidence': ['area 0.0.0.10 是 totally stub area', 'missing 192.168.10.0/24'],
             'verify': 'show ospf database area 0.0.0.10\nshow route 192.168.10.0/24',
             'fix': 'edit protocols ospf\n  set area 0.0.0.10 stub\n  delete area 0.0.0.10 stub no-summaries\ncommit',
             'rollback': 'rollback 1'},
            {'rank': 2, 'cause': 'ABR 上 area-range 配置误', 'probability': 0.1,
             'verify': 'show ospf area-range',
             'fix': 'set ospf area 0 area-range 192.168.0.0/16 restrict'},
            {'rank': 3, 'cause': 'router-id 冲突导致 ABR 失效', 'probability': 0.05,
             'verify': 'show ospf router-id',
             'fix': 'router-id 配置每台独立'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://www.juniper.net/documentation/junos-21.2/ospf-stub', 'version': '21.2R1'}],
    },
    'anti_examples': ['请重启', '删 area 0.0.0.10 重建', '改 area 0.0.0.0'],
    'grading_rubric': {
        'must_have': ['诊断 stub no-summaries', '修复：no-summaries'],
        'nice_to_have': ['area-range 配置'],
        'penalty': ['重启'],
    },
})

print('...OSPF 5 done')
