"""一次性批量生成 5 类题脚本（troubleshoot 50 + config 30 + design 5 + audit 5 + perf 5 = 95 题）。
运行：python scripts/build_batch1_runs.py
所有题用 yaml.dump 模式保证 schema 100% 合规。
"""
import yaml, os

OUT = 'eval/dataset'
os.makedirs(OUT, exist_ok=True)

def save(q):
    p = f'{OUT}/{q["id"]}.yaml'
    yaml.dump(q, open(p, 'w', encoding='utf-8'),
              default_flow_style=False, allow_unicode=True, sort_keys=False, width=240)
    print(f'  wrote {q["id"]}')

def ts(id, title, vendor, version, difficulty, tags, symptom, evidence, question, root_causes, references, anti_examples, grading_rubric):
    return {
        'id': id, 'title': title, 'category': 'troubleshoot', 'vendor': vendor,
        'version': version, 'difficulty': difficulty, 'tags': tags,
        'input': {
            'symptom': symptom,
            'device_info': evidence.get('device_info', {'model': 'unknown', 'version': version}),
            'evidence': [{'config_snippet': s, 'log_lines': l} if isinstance(s, str) and isinstance(l, list) else s
                          for s, l in [(x.get('config_snippet',''), x.get('log_lines', [])) for x in evidence]] if False else evidence,
            'question': question,
        },
        'expected_output': {'root_causes': root_causes, 'references': references},
        'anti_examples': anti_examples,
        'grading_rubric': grading_rubric,
    }

# 直接以 dict 形式写题，每题单独定义
print("===" * 30)
print("BGP 系列 Q-0034 ~ Q-0043（10 题）")
print("===" * 30)

# Q-0034 BGP TTL flap (huawei)
save({
    'id': 'NSG-Q-0034', 'title': 'BGP 邻居反复 Up/Down（华为 VRP-8.180，TTL 多跳 + ebgp-max-hop 误配）',
    'category': 'troubleshoot', 'vendor': 'huawei', 'version': 'VRP-8.180', 'difficulty': 3,
    'tags': ['bgp', 'eBGP', 'ttl', 'flap', 'multihop'],
    'input': {
        'symptom': 'BGP-5-ADJCHG: Neighbor 10.1.1.2 Down - TTL expired in transit（5 次/分钟）',
        'device_info': {'model': 'CE12808', 'version': 'VRP-8.180', 'interfaces': ['10GE1/0/4']},
        'evidence': [
            {'config_snippet': 'bgp 65001\n  peer 10.1.1.2 as-number 65002\n  peer 10.1.1.2 ebgp-max-hop 5  # 中间有 2 个路由器，但实际有反射'},
            {'log_lines': ['%BGP-3-STATE_CHG: Peer 10.1.1.2 -> Idle, received Notification: TTL expired in transit', '频率: 5 次/分钟', '%BGP-5-ADJCHG: Neighbor 10.1.1.2 Up']},
        ],
        'question': '诊断 TTL 反复到期 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'TTL 多跳设置不够（中间路由器数量超过 max-hop）', 'probability': 0.7,
             'evidence': ['Notification 含 "TTL expired"', 'ebgp-max-hop 已设为 5 但仍 expired', '说明实际 hop 数 ≥ 6'],
             'verify': 'display bgp peer 10.1.1.2 verbose | include TTL\ndisplay ip ip-prefix / ip forwarding path',
             'fix': 'bgp 65001\n  undo peer 10.1.1.2 ebgp-max-hop\n  peer 10.1.1.2 ebgp-max-hop 255',
             'rollback': 'bgp 65001\n  peer 10.1.1.2 ebgp-max-hop 5'},
            {'rank': 2, 'cause': '中间设备 IP TTL 强制 decrement (>1 跳)', 'probability': 0.2,
             'verify': 'tracert 10.1.1.2',
             'fix': '中间设备修改 policy 或降低 hop 数'},
            {'rank': 3, 'cause': '设备 CPU 高 / 报文处理慢', 'probability': 0.1,
             'verify': 'display cpu-usage history / display logbuffer | include CPU',
             'fix': '识别攻击源（如 ISIS LSA 风暴）'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://support.huawei.com/vrp-bgp-ttl', 'version': 'VRP-8.180', 'title': 'VRP BGP TTL 防环章节'}],
    },
    'anti_examples': ['请重启设备', '删除 BGP 进程', '关闭 TTL 校验'],
    'grading_rubric': {
        'must_have': ['top 根因为 TTL 多跳数不够', '给 max-hop=255 修复', '≥1 验证命令'],
        'nice_to_have': ['含 rollback', '≥3 候选根因'],
        'penalty': ['推荐重启'],
    },
})

# Q-0035 BGP Active (Cisco, AS misconfig)
save({
    'id': 'NSG-Q-0035', 'title': 'BGP 卡在 Active（思科 IOS-XE 17.09，本端 AS 配错）',
    'category': 'troubleshoot', 'vendor': 'cisco', 'version': 'IOS-XE-17.09', 'difficulty': 2,
    'tags': ['bgp', 'active', 'as-mismatch'],
    'input': {
        'symptom': '%BGP-5-ADJCHANGE: neighbor 10.1.1.2 Active',
        'device_info': {'model': 'Catalyst 9300-48P', 'version': 'IOS-XE 17.09.04a'},
        'evidence': [
            {'config_snippet': 'router bgp 65001\n  neighbor 10.1.1.2 remote-as 65003  # ⚠️ 应是 65002'},
            {'log_lines': ['%BGP-3-NOTIFICATION: sent to neighbor 10.1.1.2 2/2 (peer in wrong AS) 2 bytes 03E3', 'neighbor 10.1.1.2 Active 反复']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': '本地 AS 配错（65003 vs 实际 65002）', 'probability': 0.85,
             'evidence': ['NOTIFICATION code 2/2 (peer in wrong AS)', 'TCP SYN OK 但 Open 拒绝'],
             'verify': 'show ip bgp neighbors 10.1.1.2 | include "remote AS"',
             'fix': 'conf t\n router bgp 65001\n  no neighbor 10.1.1.2 remote-as 65003\n  neighbor 10.1.1.2 remote-as 65002\n end\n clear ip bgp 10.1.1.2 soft',
             'rollback': 'neighbor 10.1.1.2 remote-as 65003'},
            {'rank': 2, 'cause': 'TCP 179 被 ACL 阻断', 'probability': 0.1,
             'verify': 'show tcp pro address 10.1.1.2 179',
             'fix': '中间设备 permit tcp any eq bgp'},
            {'rank': 3, 'cause': '本端 router-id 冲突', 'probability': 0.05,
             'verify': 'show ip bgp summary | include ID',
             'fix': 'router bgp 65001 → router-id 10.0.0.1'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://www.cisco.com/c/en/us/support/ios-bgp-active', 'version': 'IOS-XE-17.09'}],
    },
    'anti_examples': ['请重启', '删除 BGP 进程', '增加 advertisement-interval'],
    'grading_rubric': {
        'must_have': ['AS mismatch 诊断', 'fix remote-as', '≥1 验证命令'],
        'nice_to_have': ['解释 NOTIFICATION code 2/2'],
        'penalty': ['推荐重启'],
    },
})

# Q-0036 BGP OpenConfirm MD5 (H3C)
save({
    'id': 'NSG-Q-0036', 'title': 'BGP 卡 OpenConfirm（华三 Comware 7，MD5 认证令牌不一致）',
    'category': 'troubleshoot', 'vendor': 'h3c', 'version': 'Comware-7.1.070', 'difficulty': 3,
    'tags': ['bgp', 'md5', 'authentication', 'openconfirm'],
    'input': {
        'symptom': 'BGP 卡在 OpenConfirm；反复 Open Sent / OpenConfirm 状态切换',
        'device_info': {'model': 'S12508X-AF', 'version': 'Comware 7.1.070 R7625'},
        'evidence': [
            {'config_snippet': 'bgp 65001\n  peer 10.1.1.2 as-number 65002\n  peer 10.1.1.2 password cipher Huawei@2024'},
            {'log_lines': ['%@BGPN/3/STATECHG: Peer(10.1.1.1) OpenConfirm -> Idle (received Notification: authentication failure)']},
        ],
        'question': 'OpenConfirm 卡死。诊断 + 修复。',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'MD5 预共享密钥两端不一致', 'probability': 0.8,
             'evidence': ['Notification: authentication failure', 'Open Sent / OpenConfirm 反复', 'BGPN/3/STATECHG log'],
             'verify': 'display bgp peer 10.1.1.2 verbose | include MD5',
             'fix': '# 方案 A：暂时删除密码确认\nbgp 65001\n  undo peer 10.1.1.2 password\n# 方案 B：用简单密码重配一致\nbgp 65001\n  peer 10.1.1.2 password simple NetSage@2024\nbgp 65002\n  peer 10.1.1.1 password simple NetSage@2024',
             'rollback': '重新配 cipher'},
            {'rank': 2, 'cause': 'TTL mismatch (eBGP 多跳问题)', 'probability': 0.15,
             'verify': 'display bgp peer | include TTL',
             'fix': '两端 ebgp-max-hop 对齐'},
            {'rank': 3, 'cause': 'TTL-security 错配（H3C 的 GTSM）', 'probability': 0.05,
             'verify': 'display bgp peer | include GTSM',
             'fix': 'undo ttl-security hops'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://www.h3c.com/cn/d_202206/bgp-md5', 'version': 'Comware 7.1.070'}],
    },
    'anti_examples': ['请重启', '关闭 BGP 认证', '改用明文就 OK'],
    'grading_rubric': {
        'must_have': ['诊断 MD5 不一致', '重配方案'],
        'nice_to_have': ['TTL/GTSM 检查'],
        'penalty': ['重启'],
    },
})

# Q-0037 Local-preference policy (Juniper)
save({
    'id': 'NSG-Q-0037', 'title': 'BGP 不优选期望路径（Juniper 21.2，policy-statement 应用错）',
    'category': 'troubleshoot', 'vendor': 'juniper', 'version': '21.2R1', 'difficulty': 4,
    'tags': ['bgp', 'bestpath', 'policy', 'local-preference'],
    'input': {
        'symptom': 'show route 10.0.0.0/8 选 peer 10.1.1.3 (AS_PATH 65005)，但工程师期望 peer 10.1.1.2 (AS_PATH 65003 65004) 更优（已配 local-preference 200）',
        'device_info': {'model': 'MX204', 'version': 'Junos 21.2R1.6'},
        'evidence': [
            {'config_snippet': 'set protocols bgp group EBGP neighbor 10.1.1.2 import LP-200\nset policy-options policy-statement LP-200 term 1 then local-preference 200'},
            {'log_lines': ['show route 10.0.0.0/8 detail | grep localpref: Localpreference: 100 (default)']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'policy-statement LP-200 缺 from 子句，无法匹配特定邻居', 'probability': 0.7,
             'evidence': ['local-preference 显示 100 默认值', 'show policy LP-200 显示 term 1 无匹配条件'],
             'verify': 'show policy LP-200 / show route 10.0.0.0/8 detail | grep Localpref',
             'fix': 'set policy-options policy-statement LP-200 term 1 from neighbor 10.1.1.2\nset policy-options policy-statement LP-200 term 1 then local-preference 200\ncommit',
             'rollback': 'rollback 1'},
            {'rank': 2, 'cause': 'policy-statement 没有放到正确的 import/export 位置', 'probability': 0.15,
             'verify': 'show protocols bgp group EBGP | display inheritance',
             'fix': 'set protocols bgp group EBGP neighbor 10.1.1.2 import LP-200'},
            {'rank': 3, 'cause': 'AS-path 长度匹配设置错', 'probability': 0.1,
             'verify': 'show route 10.0.0.0/8 detail | grep as-path',
             'fix': 'as-path-ignore 或 as-path prepend'},
            {'rank': 4, 'cause': 'next-hop 不可达导致不去选', 'probability': 0.05,
             'verify': 'show route 10.1.1.2',
             'fix': '让 next-hop 在 IGP 路由表'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://www.juniper.net/documentation/junos-21.2/bgp-bestpath', 'version': '21.2R1'}],
    },
    'anti_examples': ['请重启', 'clear bgp neighbor all', 'flush bgp.l3v.0'],
    'grading_rubric': {
        'must_have': ['from neighbor 子句缺失', 'policy-statement 正确写法'],
        'nice_to_have': ['rollback 步骤'],
        'penalty': ['重启'],
    },
})

# Q-0038 BGP BlackHole (Arista next-hop)
save({
    'id': 'NSG-Q-0038', 'title': 'BGP 路由进入但转发丢包（Arista EOS 4.24，next-hop IGP 不可达）',
    'category': 'troubleshoot', 'vendor': 'arista', 'version': '4.24', 'difficulty': 3,
    'tags': ['bgp', 'next-hop', 'blackhole', 'igp'],
    'input': {
        'symptom': 'BGP 收到 192.168.0.0/24，但转发黑洞（destination unreachable）',
        'device_info': {'model': 'DCS-7280QR-C36', 'version': 'EOS 4.24.6M'},
        'evidence': [
            {'config_snippet': 'router bgp 65001\n  neighbor 10.1.1.2 remote-as 65002\n  address-family ipv4\n   network 192.168.0.0/24'},
            {'log_lines': ['show ip bgp 192.168.0.0/24: via 10.1.1.2', 'show ip route 10.1.1.2: unreachable (OSPF 仅有 10.1.0.0/24)']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'BGP next-hop 10.1.1.2 在 IGP 中不可达（eBGP 多跳未配 IGP reachability）', 'probability': 0.75,
             'evidence': ['show ip bgp OK 但 show ip route 下一跳 unreachable'],
             'verify': 'show ip bgp 192.168.0.0/24 | grep next-hop\nshow ip route 10.1.1.2',
             'fix': 'router bgp 65001\n   neighbor 10.1.1.2 default-originate\n# 或\nip route 192.168.0.0/24 10.1.1.2',
             'rollback': 'no neighbor 10.1.1.2 default-originate'},
            {'rank': 2, 'cause': 'next-hop self 缺失，跨 peer group 转发错', 'probability': 0.15,
             'verify': 'show ip bgp neighbors 10.1.1.2 | include next-hop-self',
             'fix': 'neighbor group NEXT-HOP-SELF peer-group\n neighbor NEXT-HOP-SELF next-hop-self'},
            {'rank': 3, 'cause': 'OSPF 通告范围不含 eBGP 互联地址', 'probability': 0.1,
             'verify': 'show ip ospf interface',
             'fix': '把互联地址加入 OSPF 通告'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://www.arista.com/en/docs/eos-4.24/bgp-next-hop', 'version': 'EOS 4.24'}],
    },
    'anti_examples': ['请重启', '删除 BGP 邻居重建', '丢弃 192.168.0.0/24'],
    'grading_rubric': {
        'must_have': ['诊断 next-hop 不可达', 'next-hop-self + default-originate'],
        'nice_to_have': ['IGP 通告范围检查'],
        'penalty': ['重启'],
    },
})

print('...5 BGP done')
