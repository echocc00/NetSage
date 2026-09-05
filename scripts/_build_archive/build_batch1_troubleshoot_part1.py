"""
批量生成 NSG-Q-0034 ~ 0083 的 troubleshoot 题（50 题，对应 v0.1.3 batch1）。

按出题指南 §3.1 场景清单分五大类：
- BGP (10 题): neighbor flap / idle / openconfirm / route not best / blackhole / prefix-limit / leak / ebgp-ibgp / ipv6 / evpn
- OSPF (10 题): hello/MTU/CRC, init/2-way (area/auth/mask), exstart (MTU/priority), loading (DBD/LSA)
- VXLAN/EVPN (10 题): Type-2 ARP/MAC/VNI, Type-3 peer/activate, BUM anycast-gateway
- VPN (8 题): IPsec tunnel no-build, IPsec tunnel flap, IPsec passthrough, SSL VPN auth
- interface (5 题): down/CRC/duplex, vlan/trunk/allowed, Eth-trunk/LACP

每个具体题目都是 (vendor, version, scenario) 三元组 + standard evidence。

格式：yaml.dump 模式（已验证 schema 100%）
"""
import yaml, os

OUT = 'eval/dataset'

def build_q(base):
    """base dict 直接转 yaml 输出"""
    return base

def save(q, path):
    yaml.dump(q, open(path, 'w', encoding='utf-8'),
              default_flow_style=False, allow_unicode=True, sort_keys=False, width=240)

# ==========================================
# BGP — 10 题 (NSG-Q-0034 ~ 0043)
# ==========================================

BGP_NeighborFlap_Huawei = {
    'id': 'NSG-Q-0034',
    'title': 'BGP 邻居反复 Up/Down（华为 VRP-8.180，TTL=1 链路安全检查）',
    'category': 'troubleshoot',
    'vendor': 'huawei',
    'version': 'VRP-8.180',
    'difficulty': 3,
    'tags': ['bgp', 'eBGP', 'ttl', 'flap', 'multihop'],
    'input': {
        'symptom': 'BGP-5-ADJCHG: Neighbor 10.1.1.2 Down - TTL expired in transit (重复 Up/Down)',
        'device_info': {'model': 'CE12800', 'version': 'VRP-8.180', 'interfaces': ['10GE1/0/4']},
        'evidence': [
            {'config_snippet': 'bgp 65001\n  peer 10.1.1.2 as-number 65002\n  peer 10.1.1.2 ebgp-max-hop 5  # 多跳但中间有反射'},
            {'log_lines': [
                '%%01BGP/3/STATE_CHG: Peer 10.1.1.2 -> Idle, received Notification: TTL expired in transit',
                '%%01BGP/5/ADJCHG: Neighbor 10.1.1.2 Up',
                '频率: 5 次/分钟'
            ]},
        ],
        'question': 'BGP 邻居反复 Up/Down（约 5 次/分钟），log 显示 TTL expired。检查根因 + 给出修复。',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'TTL 默认 1，但 BGP 报文经过中间路由（实际是多跳场景未配 ebgp-max-hop）', 'probability': 0.7,
             'evidence': ['ebgp-max-hop 已配为 5，但 Notification 中仍报 TTL expired 表明仍有中间路由器封装/解封装丢失'],
             'verify': 'display bgp peer 10.1.1.2 verbose | include TTL / max-hop',
             'fix': 'bgp 65001 → undo peer 10.1.1.2 ebgp-max-hop → peer 10.1.1.2 ebgp-max-hop 255\n# 同步检查两侧设备的 path-mtu',
             'rollback': 'bgp 65001 → peer 10.1.1.2 ebgp-max-hop 5'},
            {'rank': 2, 'cause': '中间设备做端口安全（Port-Security）/ DHCP Snooping 阻断', 'probability': 0.2,
             'verify': 'display interface | include drop / display logbuffer | include drop',
             'fix': '在 transit 交换机上放行 BGP source IP 与 port 179'},
            {'rank': 3, 'cause': '设备 CPU 高 / 丢包风暴', 'probability': 0.1,
             'verify': 'display cpu-usage history / display interface | include CRC',
             'fix': '识别攻击源或路由收敛风暴（display logbuffer | include attack）'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://support.huawei.com/vrp-bgp-ttl', 'version': 'VRP-8.180', 'title': 'VRP 8.180 BGP ebgp-max-hop + TTL 防环'}],
    },
    'anti_examples': ['请重启设备', '删除 BGP 进程', '关闭 TTL 校验'],
    'grading_rubric': {
        'must_have': ['top 根因为 TTL 多跳未对齐', '修复方案给 max-hop 值', '≥1 验证命令'],
        'nice_to_have': ['含 rollback', '≥3 候选根因'],
        'penalty': ['推荐重启', '删除 BGP'],
    },
}

BGP_Idle_Active_Cisco = {
    'id': 'NSG-Q-0035',
    'title': 'BGP 卡在 Active 状态（思科 IOS-XE 17.09，AS number 配置错误）',
    'category': 'troubleshoot',
    'vendor': 'cisco',
    'version': 'IOS-XE-17.09',
    'difficulty': 2,
    'tags': ['bgp', 'active', 'as-mismatch'],
    'input': {
        'symptom': '%BGP-5-ADJCHANGE: neighbor 10.1.1.2 Active',
        'device_info': {'model': 'Catalyst 9300-48P', 'version': 'IOS-XE 17.09.04a', 'interfaces': ['GigabitEthernet1/0/24']},
        'evidence': [
            {'config_snippet': 'router bgp 65001\n neighbor 10.1.1.2 remote-as 65003  # ⚠️ 应是 65002'},
            {'log_lines': ['%BGP-3-NOTIFICATION: sent to neighbor 10.1.1.2 2/2 (peer in wrong AS) 2 bytes 03E3', 'neighbor 10.1.1.2 Active']},
        ],
        'question': 'BGP 邻居持续 Active；log 显示 "peer in wrong AS"。诊断修复。',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'AS 号配置错误（本地配 65003，实际对端是 65002）', 'probability': 0.85,
             'evidence': ['Notification code 2/2 (AS mismatch)', 'Active 状态反复但 TCP 三次握手 OK'],
             'verify': 'show ip bgp neighbors 10.1.1.2 | include remote AS',
             'fix': 'conf t\n router bgp 65001\n  no neighbor 10.1.1.2 remote-as 65003\n  neighbor 10.1.1.2 remote-as 65002\n end\n clear ip bgp 10.1.1.2 soft',
             'rollback': 'neighbor 10.1.1.2 remote-as 65003'},
            {'rank': 2, 'cause': 'TCP 179 被中间设备阻断', 'probability': 0.1,
             'verify': 'show ip bgp tcp-ia address 10.1.1.2 179',
             'fix': '放行 BGP 端口'},
            {'rank': 3, 'cause': '本地 router-id 冲突', 'probability': 0.05,
             'verify': 'show ip bgp summary | include ID',
             'fix': 'router bgp 65001 → router-id 10.0.0.1 强制设'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://www.cisco.com/c/en/us/support/ios-bgp-active', 'version': 'IOS-XE-17.09'}],
    },
    'anti_examples': ['请重启', '删除 BGP 进程', '增加 advertisement-interval'],
    'grading_rubric': {
        'must_have': ['AS 号不匹配', 'fix remote-as 配置', '≥1 验证命令'],
        'nice_to_have': ['解释 NOTIFICATION code 2/2'],
        'penalty': ['推荐重启', '忽略 AS 不匹配'],
    },
}

BGP_OpenConfirm_H3C = {
    'id': 'NSG-Q-0036',
    'title': 'BGP 卡 OpenConfirm（华三 Comware 7，MD5 认证令牌不一致）',
    'category': 'troubleshoot',
    'vendor': 'h3c',
    'version': 'Comware-7.1.070',
    'difficulty': 3,
    'tags': ['bgp', 'md5', 'authentication', 'openconfirm'],
    'input': {
        'symptom': 'BGP 卡在 OpenConfirm；反复 Open Sent / OpenConfirm 状态切换',
        'device_info': {'model': 'S12508X-AF', 'version': 'Comware 7.1.070 R7625'},
        'evidence': [
            {'config_snippet': '# Spoke-A\nbgp 65001\n peer 10.1.1.2 as-number 65002\n peer 10.1.1.2 password cipher Huawei123'},
            {'config_snippet': '# Spoke-B\nbgp 65002\n peer 10.1.1.1 as-number 65001\n peer 10.1.1.1 password cipher Juniper456  # ⚠️ 不一致'},
            {'log_lines': ['%@BGPN/3/STATECHG: Peer(10.1.1.1) OpenConfirm -> Idle (received Notification: authentication failure)']},
        ],
        'question': 'OpenConfirm 卡死。诊断 + 修复。',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'MD5 预共享密钥不一致（cipher hash 不同）', 'probability': 0.8,
             'evidence': ['Notification: authentication failure', 'Open Sent / OpenConfirm 反复'],
             'verify': 'display bgp peer 10.1.1.2 verbose | include MD5',
             'fix': '# 方案 A：暂时删除密码验证\nbgp 65001\n undo peer 10.1.1.2 password\n# 方案 B：用明文重新配置一致\nbgp 65001\n peer 10.1.1.2 password simple NetSage2024\nbgp 65002\n peer 10.1.1.1 password simple NetSage2024',
             'rollback': '重新配回 cipher 密码'},
            {'rank': 2, 'cause': 'TTL mismatch (eBGP 多跳问题)', 'probability': 0.15,
             'verify': 'display bgp peer | include TTL',
             'fix': '两端 ebgp-max-hop 一致'},
            {'rank': 3, 'cause': 'TTL-security 错配（H3C 的 GTSM）', 'probability': 0.05,
             'verify': 'display bgp peer | include GTSM',
             'fix': 'undo ttl-security hops + ebgp-max-hop 对齐'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://www.h3c.com/cn/d_202206/bgp-md5', 'version': 'Comware 7.1.070'}],
    },
    'anti_examples': ['请重启', '关闭 BGP 认证', '改用明文就 OK'],
    'grading_rubric': {
        'must_have': ['诊断 MD5 不一致', '提供对比 + 重配建议'],
        'nice_to_have': ['TTL GTSM 检查'],
        'penalty': ['重启设备'],
    },
}

BGP_RouteNotBest_Juniper = {
    'id': 'NSG-Q-0037',
    'title': 'BGP 不选最优路由（Juniper 21.2，local-preference + as-path 长度优先）',
    'category': 'troubleshoot',
    'vendor': 'juniper',
    'version': '21.2R1',
    'difficulty': 4,
    'tags': ['bgp', 'bestpath', 'policy', 'as-path', 'local-preference'],
    'input': {
        'symptom': 'show route 10.0.0.0/8 显示从 peer 10.1.1.2 收到路径 (AS_PATH 65003 65004)，但未优选；从 peer 10.1.1.3 收到 (AS_PATH 65005)，被优选。但工程师期望路径 1 (65003 65004) 更优。',
        'device_info': {'model': 'MX204', 'version': 'Junos 21.2R1.6'},
        'evidence': [
            {'config_snippet': 'set protocols bgp group EBGP neighbor 10.1.1.2 import LP-200\nexit\n\npolicy-options policy-statement LP-200 from neighbor 10.1.1.2\nset policy-options policy-statement LP-200 then local-preference 200'},
            {'config_snippet': '# peer 10.1.1.3 的 import policy 未配'},
            {'log_lines': ['show route 10.0.0.0/8: 10.1.1.3 > 10.1.1.2 (active available)']},
        ],
        'question': '诊断为什么路径 1 未优选，给出修复。',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'Local preference 实际被识别为最低 (100 默认)，而非 200。policy-statement 应用顺序错或正则匹配错。', 'probability': 0.65,
             'evidence': ['policy-statement LP-200 应该应用在 neighbor 上，但 import 时未和 prefix-list/AS-path filter 配合', 'show route protocol: 实际 metric 仍为 100'],
             'verify': 'show policy LP-200 / show route 10.0.0.0/8 extensive | match localpref',
             'fix': 'set policy-options policy-statement LP-200 term 1 from neighbor 10.1.1.2\nset policy-options policy-statement LP-200 term 1 then local-preference 200\nset protocols bgp group EBGP neighbor 10.1.1.2 import LP-200\ncommit',
             'rollback': 'rollback 1'},
            {'rank': 2, 'cause': 'AS-path 长度更优被误解 — 实际上 Juniper 默认走 shortest as-path, 但需要 `as-path-ignore` 才正确', 'probability': 0.2,
             'verify': 'show route 10.0.0.0/8 detail | match as-path',
             'fix': 'set policy-options as-path AS200 "<as-path>"\nset policy-options policy-statement PEER1-2 from as-path AS200\nset policy-options policy-statement PEER1-2 then local-preference 200'},
            {'rank': 3, 'cause': 'EBGP 多跳链路默认 TTL=1 路径丢弃', 'probability': 0.1,
             'verify': 'show bgp neighbor 10.1.1.2 | match TTL',
             'fix': 'set protocols bgp group EBGP multihop ttl 255 neighbor 10.1.1.2'},
            {'rank': 4, 'cause': 'MED、origin code 未匹配 policy', 'probability': 0.05,
             'verify': 'show route 10.0.0.0/8 detail | match origin',
             'fix': 'policy-statement 加 from med 4 / from origin igp'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://www.juniper.net/documentation/junos-21.2/bgp-bestpath', 'version': '21.2R1'}],
    },
    'anti_examples': ['请重启', 'flush bgp.l3v.0', 'cmd > clear bgp session'],
    'grading_rubric': {
        'must_have': ['诊断 Local preference 未生效', 'policy-statement 正确写', 'rollback'],
        'nice_to_have': ['as-path-ignore 说明', 'multihop 修正'],
        'penalty': ['重启服务'],
    },
}

BGP_BlackHole_Arista = {
    'id': 'NSG-Q-0038',
    'title': 'BGP next-hop 不可达导致流量黑洞（Arista EOS 4.24，IGP miss）',
    'category': 'troubleshoot',
    'vendor': 'arista',
    'version': '4.24',
    'difficulty': 3,
    'tags': ['bgp', 'next-hop', 'blackhole', 'igp'],
    'input': {
        'symptom': 'BGP 收到 192.168.0.0/24 路由，但实际转发丢包（黑洞）。',
        'device_info': {'model': 'DCS-7280QR-C36', 'version': 'EOS 4.24.6M'},
        'evidence': [
            {'config_snippet': 'router bgp 65001\n neighbor 10.1.1.2 remote-as 65002\n address-family ipv4\n  network 192.168.0.0/24'},
            {'log_lines': ['show ip route 192.168.0.0/24: via 10.1.1.2 (BGP)', '但 show ip route 10.1.1.2: unreachable / path via OSPF says no route to 10.1.0.0/24']},
        ],
        'question': '诊断 + 修复。',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'BGP next-hop 10.1.1.2 在 IGP 中不可达（常见场景：eBGP 多跳未配 IGP）', 'probability': 0.75,
             'evidence': ['BGP 选路 OK 但 IGP 无 10.1.0.0/24 路径'],
             'verify': 'show ip bgp 192.168.0.0/24 | match next-hop\nshow ip route 10.1.1.2',
             'fix': 'router bgp 65001\n neighbor 10.1.1.2 remote-as 65002\n neighbor 10.1.1.2 default-originate  # 推默认路由\n# 或\ngenerate route 192.168.0.0/24 10.1.1.2',
             'rollback': 'no neighbor ... default-originate'},
            {'rank': 2, 'cause': 'BGP next-hop self 缺失，跨 peer group 转发路径错', 'probability': 0.15,
             'verify': 'show ip bgp neighbors 10.1.1.2 | include next-hop-self',
             'fix': 'neighbor group NEXT-HOP-SELF peer-group\n neighbor NEXT-HOP-SELF next-hop-self'},
            {'rank': 3, 'cause': 'OSPF 中下层 EBGP peer IP 不在 OSPF 通告范围', 'probability': 0.1,
             'verify': 'show ip ospf interface',
             'fix': '把 EBGP 互联地址纳入 OSPF 通告'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://www.arista.com/en/docs/eos-4.24/bgp-next-hop', 'version': 'EOS 4.24'}],
    },
    'anti_examples': ['请重启', 'delete BGP 邻居重建', '丢弃 192.168.0.0/24'],
    'grading_rubric': {
        'must_have': ['诊断 next-hop 不可达', 'next-hop-self 配置'],
        'nice_to_have': ['IGP 通告范围检查'],
        'penalty': ['重启'],
    },
}

# 下一组 5 个 BGP 场景接着输出（prefix-limit、route-leak、ipv6、evpn、capability）
# 限于篇幅直接用脚本生成。调用 save() 循环写出所有题目
BGP_Capability_Cisco = {
    'id': 'NSG-Q-0039',
    'title': 'BGP capability 协商失败（Cisco IOS-XE 17，地址族未 activate）',
    'category': 'troubleshoot',
    'vendor': 'cisco',
    'version': 'IOS-XE-17.09',
    'difficulty': 3,
    'tags': ['bgp', 'capability', 'address-family', 'ipv6'],
    'input': {
        'symptom': 'IPv6 BGP peer 1999::2 OpenConfirm 卡住；IPv4 邻居正常。',
        'device_info': {'model': 'ASR 1001-X', 'version': 'IOS-XE 17.09.04a'},
        'evidence': [
            {'config_snippet': 'router bgp 65001\n neighbor 1999::2 remote-as 65002\n ! ⚠️ 缺 address-family ipv6 unicast\n address-family ipv4 unicast\n  neighbor 1999::2 activate   # 错配在 v4 family 内'},
            {'log_lines': ['%BGP-5-ADJCHANGE: neighbor 1999::2 Up', 'OpenConfirm → Idle: "no matching interface-protocol"']},
        ],
        'question': '诊断 + 修复。',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'IPv6 地址族未独立 activate（v4 family 内 activate 不生效）', 'probability': 0.85,
             'evidence': ['路由器日志 "no matching interface-protocol"', 'OpenConfirm 卡住'],
             'verify': 'show ip bgp neighbors 1999::2 | include AFI / IPv6',
             'fix': 'router bgp 65001\n address-family ipv6 unicast\n  neighbor 1999::2 activate\n exit-address-family',
             'rollback': 'address-family ipv6 unicast → no neighbor 1999::2 activate'},
            {'rank': 2, 'cause': 'MP-BGP capability 协商问题', 'probability': 0.1,
             'verify': 'show ip bgp neighbors 1999::2 | include capability',
             'fix': 'no neighbor 1999::2 capability mp-bgp → 无用，应 enable both address-family'},
            {'rank': 3, 'cause': 'IPv6 链路不通（不存在 IPv6 路由）', 'probability': 0.05,
             'verify': 'show ipv6 route 1999::2',
             'fix': '给互联接口配置 IPv6 地址 + 启用 IPv6 routing'},
        ],
        'references': [{'type': 'rfc', 'url': 'https://datatracker.ietf.org/doc/html/rfc2545', 'title': 'BGP-4 MP for IPv6'}],
    },
    'anti_examples': ['请重启', '改成 IPv4 邻居', '关闭 IPv6 协议'],
    'grading_rubric': {
        'must_have': ['诊断地址族未独立 activate', '修复：address-family ipv6 unicast activate'],
        'nice_to_have': ['RFC 2545 引用'],
        'penalty': ['重启'],
    },
}

BGP_MaximumPrefix_Huawei = {
    'id': 'NSG-Q-0040',
    'title': 'BGP maximum-prefix 超限（华为 VRP-8.180，peer 邻居被自动 shutdown）',
    'category': 'troubleshoot',
    'vendor': 'huawei',
    'version': 'VRP-8.180',
    'difficulty': 3,
    'tags': ['bgp', 'prefix-limit', 'route-flap'],
    'input': {
        'symptom': 'BGP 邻居被强制 Idle 状态，显示 "%BGP-3-MAXPFX_EXCEEDED"',
        'device_info': {'model': 'NE40E-X8A', 'version': 'VRP-8.180'},
        'evidence': [
            {'config_snippet': 'bgp 65001\n peer 10.1.1.2 as-number 65002\n peer 10.1.1.2 maximum-prefix 1000 80  # 上限 1000，恢复阈值 80%\n# 当前对端发来 5000 前缀（路由泄漏/被攻击/上游扩容）'},
            {'log_lines': ['%BGP-3-MAXPFX_EXCEEDED: Peer 10.1.1.2 exceeded maximum-prefix limit 1000', 'Peer 10.1.1.2 -> Idle']},
        ],
        'question': '诊断 + 给出修复与预防。',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': '对端 BG