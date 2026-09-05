"""VXLAN+VPN+interface+static_route 共 20 题 (Q-0049~0068).
注意：5 道 compact 写法，每题用 yaml.dump."""
import yaml, os
OUT = 'eval/dataset'

def save(q):
    p = f'{OUT}/{q["id"]}.yaml'
    yaml.dump(q, open(p, 'w', encoding='utf-8'),
              default_flow_style=False, allow_unicode=True, sort_keys=False, width=240)
    print(f'  wrote {q["id"]}')

# Q-0049 VXLAN Type-2 MAC 不学习 Cisco
save({
    'id': 'NSG-Q-0049', 'title': 'VXLAN Type-2 MAC 不互通（思科 NX-OS 9.3，EVPN instance 漏配 l2vpn evpn instance）',
    'category': 'troubleshoot', 'vendor': 'cisco', 'version': 'NX-OS-9.3', 'difficulty': 4,
    'tags': ['vxlan', 'evpn', 'type-2', 'mac'],
    'input': {
        'symptom': '同 VNI 10010 跨 Leaf，VM MAC 地址学习不到',
        'device_info': {'model': 'Nexus 9336C-FX2', 'version': 'NX-OS 9.3(8)'},
        'evidence': [
            {'config_snippet': 'feature nv overlay\nfeature vn-segment-vlan-based\nl2vpn evpn   # ⚠️ 没建 evpn instance\nrouter bgp 65000\n  address-family l2vpn evpn\n    neighbor 10.0.0.1 activate'},
            {'log_lines': ['show l2vpn evpn summary: total instances 0', 'show nve vni 10010: L2VNI information not found']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': '未配置 l2vpn evpn instance；type-2 路由无法 reachability', 'probability': 0.7,
             'evidence': ['show l2vpn evpn summary 显示 0 instances'],
             'verify': 'show l2vpn evpn summary / show nve vni',
             'fix': 'conf t\n  l2vpn evpn instance 10 point-to-point\n   rd 10.0.0.1:10\n   route-target import 65000:10010\n   route-target export 65000:10010\n   encapsulate vxlan\n  end',
             'rollback': 'no l2vpn evpn instance 10'},
            {'rank': 2, 'cause': 'NVE 接口未配置 member vni', 'probability': 0.2,
             'verify': 'show nve interface nve 1 detail',
             'fix': 'interface nve1\n  member vni 10010\n   ingress-replication protocol bgp'},
            {'rank': 3, 'cause': 'BGP EVPN address-family 漏激活', 'probability': 0.1,
             'verify': 'show bgp l2vpn evpn summary',
             'fix': 'router bgp 65000\n  address-family l2vpn evpn\n   neighbor 10.0.0.1 activate'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://www.cisco.com/c/en/us/td/docs/switches/datacenter/sw/nx-os/vxlan', 'version': 'NX-OS-9.3'}],
    },
    'anti_examples': ['请重启', '改 VNI', '删除 nve 重建'],
    'grading_rubric': {
        'must_have': ['诊断 instance 漏配', 'l2vpn evpn instance 配置'],
        'nice_to_have': ['BGP activate 检查'],
        'penalty': ['重启'],
    },
})

# Q-0050 VXLAN Type-3 BGP peer H3C
save({
    'id': 'NSG-Q-0050', 'title': 'VXLAN Type-3 BUM 不通（华三 Comware 7，BGP l2vpn evpn peer enable 漏配）',
    'category': 'troubleshoot', 'vendor': 'h3c', 'version': 'Comware-7.1.070', 'difficulty': 4,
    'tags': ['vxlan', 'evpn', 'type-3', 'bgp', 'enable'],
    'input': {
        'symptom': 'BUM 流量跨 Leaf 不通；Type-3 路由学习不到',
        'device_info': {'model': 'S9850-32B', 'version': 'Comware 7.1.070 R7625'},
        'evidence': [
            {'config_snippet': 'bgp 65000\n  peer 10.0.0.1 as-number 65000\n  ! ⚠️ 缺 address-family l2vpn evpn / peer enable'},
            {'log_lines': ['display bgp l2vpn evpn peer: no peer established family', 'display evpn route: 只有本端 Type-3']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'address-family l2vpn evpn 下未 peer 10.0.0.1 enable', 'probability': 0.7,
             'evidence': ['bgp l2vpn evpn no peer family'],
             'verify': 'display bgp l2vpn evpn peer\ndisplay evpn route',
             'fix': 'bgp 65000\n  address-family l2vpn evpn\n   peer 10.0.0.1 enable\n  quit',
             'rollback': 'address-family l2vpn evpn → undo peer 10.0.0.1 enable'},
            {'rank': 2, 'cause': 'EVPN instance 漏配', 'probability': 0.2,
             'verify': 'display evpn instance',
             'fix': 'evpn instance evi-10\n  vxlan vni 10010\n  route-target 65000:10010 both'},
            {'rank': 3, 'cause': 'nve peer 不通', 'probability': 0.1,
             'verify': 'display nve peer',
             'fix': '检查 BGP 互联可达性'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://www.h3c.com/cn/d_202206/evpn-type3', 'version': 'Comware 7.1.070'}],
    },
    'anti_examples': ['请重启', '改 instance id', '删除 nve'],
    'grading_rubric': {
        'must_have': ['诊断 BGP enable 缺失', '修复 peer enable'],
        'nice_to_have': ['instance 检查'],
        'penalty': ['重启'],
    },
})

# Q-0051 IPsec Phase-1 SA Huawei
save({
    'id': 'NSG-Q-0051', 'title': 'IPsec Phase-1 协商失败（华为 USG 6680，IKE proposal 与对端不重叠）',
    'category': 'troubleshoot', 'vendor': 'huawei', 'version': 'VRP-8.180', 'difficulty': 4,
    'tags': ['ipsec', 'ike', 'phase1', 'proposal'],
    'input': {
        'symptom': 'IKE_SA_INIT: NO_PROPOSAL_CHOSEN；IPsec 隧道不起',
        'device_info': {'model': 'USG 6680', 'version': 'VRP-8.180'},
        'evidence': [
            {'config_snippet': 'ike proposal 1\n  encryption-algorithm aes-cbc-256\n  integrity sha2-256\n  dh group 14\n  authentication-method pre-share\n# 对端 only aes-gcm-256 group 15'},
            {'log_lines': ['IKE: NO_PROPOSAL_CHOSEN 收到', 'display ike sa: 没有活跃 SA']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'IKE proposal 算法集合与对端无交集', 'probability': 0.85,
             'evidence': ['NO_PROPOSAL_CHOSEN 告警'],
             'verify': 'display ike proposal\ndisplay ike sa',
             'fix': 'ike proposal 2\n  encryption-algorithm aes-cbc-256 aes-gcm-256\n  integrity sha2-256 sha2-384\n  dh group 14 group 15\n  authentication-method pre-share\n# 删除原 proposal 1，叠加自定义到 2',
             'rollback': 'undo ike proposal 2'},
            {'rank': 2, 'cause': 'authentication-method 不匹配', 'probability': 0.1,
             'verify': 'display ike peer | include auth',
             'fix': 'authentication-method 改为 pre-share / rsa-signature 一致'},
            {'rank': 3, 'cause': 'pre-shared-key 不一致', 'probability': 0.05,
             'verify': 'display ike peer',
             'fix': '对齐 pre-shared-key'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://support.huawei.com/vrp-ipsec-ike', 'version': 'VRP-8.180'}],
    },
    'anti_examples': ['请重启', '关闭 IPsec', '删 tunnel'],
    'grading_rubric': {
        'must_have': ['诊断 NO_PROPOSAL_CHOSEN', '修改 ike proposal 加多组算法'],
        'nice_to_have': ['dh group 解释'],
        'penalty': ['重启'],
    },
})

# Q-0052 IPsec DPD Cisco
save({
    'id': 'NSG-Q-0052', 'title': 'IPsec 隧道反复重建（思科 IOS-XE 17，DPD 抖动）',
    'category': 'troubleshoot', 'vendor': 'cisco', 'version': 'IOS-XE-17.09', 'difficulty': 4,
    'tags': ['ipsec', 'dpd', 'sa-lifetime', 'flap'],
    'input': {
        'symptom': 'IPsec 隧道反复重建（30 秒/次）',
        'device_info': {'model': 'ISR 4451-X', 'version': 'IOS-XE 17.09.04a'},
        'evidence': [
            {'config_snippet': 'crypto ikev2 profile PROF1\n  dpd 5 3 on-demand\ncrypto ipsec transform-set TSET esp-aes 256 esp-sha256-hmac\n  mode tunnel\n  lifetime 3600\n# DPD 间隔 5 秒，门限 3 次'},
            {'log_lines': ['%CRYPTO-5-DPD_PROBE: Probe failed', '%CRYPTO-4-IKE_DELETE_CHILD_SA_FAILURE']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'DPD 间隔太短 + on-demand 触发误判（中间设备抖动）', 'probability': 0.6,
             'evidence': ['DPD probe 5s 间隔太短，链路抖动被误判 tunnel down'],
             'verify': 'show crypto ikev2 sa verbose\nshow crypto ipsec sa',
             'fix': 'crypto ikev2 profile PROF1\n  dpd 30 3 on-demand  # 30 秒更稳\ncrypto ipsec transform-set TSET\n  lifetime 86400  # 24 小时',
             'rollback': 'lifetime 3600'},
            {'rank': 2, 'cause': 'Phase-2 lifetime 设过短', 'probability': 0.3,
             'verify': 'show crypto ipsec sa | include lifetime',
             'fix': 'lifetime 28800 (8h)'},
            {'rank': 3, 'cause': 'SLA 监控器误判', 'probability': 0.1,
             'verify': 'show track',
             'fix': '调整 SLA threshold'},
        ],
        'references': [{'type': 'rfc', 'url': 'https://datatracker.ietf.org/doc/html/rfc3706', 'title': 'IKE Dead Peer Detection'}],
    },
    'anti_examples': ['请重启', '关闭 DPD', '调短 lifetime'],
    'grading_rubric': {
        'must_have': ['诊断 DPD 误判', 'DPD 30s 调整'],
        'nice_to_have': ['RFC 3706 引用'],
        'penalty': ['关闭 DPD'],
    },
})

# Q-0053 interface down CRC Arista
save({
    'id': 'NSG-Q-0053', 'title': '40GE 接口频繁 flap（Arista EOS 4.24，光模块 RxPower 衰减）',
    'category': 'troubleshoot', 'vendor': 'arista', 'version': '4.24', 'difficulty': 3,
    'tags': ['interface', 'optic', 'crc', 'flap'],
    'input': {
        'symptom': 'Ethernet1 频繁 Up/Down（10 次/小时）',
        'device_info': {'model': 'DCS-7280QR-C36', 'version': 'EOS 4.24.6M'},
        'evidence': [
            {'config_snippet': 'interface Ethernet1\n  speed 40000\n  no shutdown'},
            {'log_lines': ['%LINEPROTO-5-UPDOWN: Line protocol on Interface Ethernet1, changed state to up', '重复 10 次/小时', '%ETH-4-MULT_DROP: hardware output drops']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': '光模块 RxPower 衰减（超出 tolerance）', 'probability': 0.7,
             'evidence': ['interface flap 频次高', 'output drops 伴随'],
             'verify': 'show interface ethernet1\nshow interface ethernet1 transceiver',
             'fix': '# 1. 更换光模块\n# 2. 清洁光纤端面\n# 3. 检查 link-up 抖动时间（print timing）'},
            {'rank': 2, 'cause': '光纤连接器污染', 'probability': 0.2,
             'verify': 'show transceiver',
             'fix': '清洁端面 + 重新插入'},
            {'rank': 3, 'cause': 'speed/duplex 协商不一致', 'probability': 0.1,
             'verify': 'show interface Ethernet1 status',
             'fix': '两端 speed 40000 全双工强制'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://www.arista.com/en/docs/eos-4.24/optic', 'version': 'EOS 4.24'}],
    },
    'anti_examples': ['请重启', '更换 line card', '关闭 40GE'],
    'grading_rubric': {
        'must_have': ['诊断光模块衰减', '更换 + 清洁'],
        'nice_to_have': ['transceiver 命令'],
        'penalty': ['重启'],
    },
})

# Q-0054 interface trunk Juniper
save({
    'id': 'NSG-Q-0054', 'title': 'Trunk 不通过 VNI（Juniper 21.2，VLAN ID 不一致）',
    'category': 'troubleshoot', 'vendor': 'juniper', 'version': '21.2R1', 'difficulty': 2,
    'tags': ['interface', 'vlan', 'trunk', 'mismatch'],
    'input': {
        'symptom': 'Trunk 端口 VLAN 10 不通',
        'device_info': {'model': 'EX4300', 'version': 'Junos 21.2R1.6'},
        'evidence': [
            {'config_snippet': '# Switch-A\nset interfaces ge-0/0/1 unit 0 family ethernet-switching vlan members VLAN10\n# Switch-B\nset interfaces ge-0/0/1 unit 0 family ethernet-switching vlan members VLAN1\n# ⚠️ VLAN 名/ID 不一致'},
            {'log_lines': ['show ethernet-switching table ge-0/0/1: no entries']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'VLAN 名/ID 错配', 'probability': 0.7,
             'evidence': ['switch A 是 VLAN10，switch B 是 VLAN1'],
             'verify': 'show vlans\nshow ethernet-switching table',
             'fix': 'delete interfaces ge-0/0/1 unit 0 family ethernet-switching vlan members VLAN1\nset interfaces ge-0/0/1 unit 0 family ethernet-switching vlan members VLAN10\n# 同时两端 vlans 配置一致\nset vlans VLAN10 vlan-id 10\ncommit',
             'rollback': 'rollback 0'},
            {'rank': 2, 'cause': 'native vlan 不匹配', 'probability': 0.2,
             'verify': 'show ethernet-switching options',
             'fix': 'set interfaces ge-0/0/1 unit 0 family ethernet-switching native-vlan-id 10'},
            {'rank': 3, 'cause': 'port mode 配错', 'probability': 0.1,
             'verify': 'show interfaces ge-0/0/1 | include mode',
             'fix': 'set interfaces ge-0/0/1 unit 0 family ethernet-switching interface-mode trunk'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://www.juniper.net/documentation/junos-21.2/vlan-trunk', 'version': '21.2R1'}],
    },
    'anti_examples': ['请重启', '关闭 trunk', '删除 VLAN'],
    'grading_rubric': {
        'must_have': ['诊断 VLAN 错配', '统一 VLAN ID'],
        'nice_to_have': ['native-vlan-id'],
        'penalty': ['重启'],
    },
})

# Q-0055 static_route recursive H3C
save({
    'id': 'NSG-Q-0055', 'title': '静态路由不优（华三 Comware 7，下一跳不可达）',
    'category': 'troubleshoot', 'vendor': 'h3c', 'version': 'Comware-7.1.070', 'difficulty': 2,
    'tags': ['static-route', 'recursive-lookup'],
    'input': {
        'symptom': 'ip route-static 192.168.0.0 255.255.0.0 10.0.0.1 显示 inactive',
        'device_info': {'model': 'S5731-S48P4X', 'version': 'Comware 7.1.070 R7625'},
        'evidence': [
            {'config_snippet': 'ip route-static 192.168.0.0 255.255.0.0 10.0.0.1\n# 但本端 10.0.0.0/24 不在直连段'},
            {'log_lines': ['display ip routing-table 192.168.0.0/16: inactive', '下一跳 10.0.0.1 不可达']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': '下一跳 IP 10.0.0.1 不在直连路由表', 'probability': 0.8,
             'evidence': ['路由 inactive'],
             'verify': 'display ip routing-table 10.0.0.1',
             'fix': 'ip route-static 192.168.0.0 255.255.0.0 192.168.1.1 preference 5\n# 或换出接口\nip route-static 192.168.0.0 255.255.0.0 Vlan-interface10 10.0.0.1',
             'rollback': 'undo ip route-static 192.168.0.0 255.255.0.0'},
            {'rank': 2, 'cause': '下一跳 IP 是本端接口', 'probability': 0.15,
             'verify': 'display ip interface brief',
             'fix': '改成正确的下一跳 IP'},
            {'rank': 3, 'cause': '出接口 down', 'probability': 0.05,
             'verify': 'display ip interface brief | include down',
             'fix': 'undo shutdown'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://www.h3c.com/cn/d_202206/static-route', 'version': 'Comware 7.1.070'}],
    },
    'anti_examples': ['请重启', '删除全部 route', '改 default route'],
    'grading_rubric': {
        'must_have': ['诊断下一跳不可达', '修改出接口或下一跳'],
        'nice_to_have': ['preference 调整'],
        'penalty': ['重启'],
    },
})

# Q-0056 policy_route Huawei
save({
    'id': 'NSG-Q-0056', 'title': '策略路由不匹配（华为 VRP-8.180，ACL 配置错位）',
    'category': 'troubleshoot', 'vendor': 'huawei', 'version': 'VRP-8.180', 'difficulty': 3,
    'tags': ['policy-route', 'acl', 'next-hop'],
    'input': {
        'symptom': '策略路由 rule 不匹配，源 10.1.0.0/16 未走 192.168.10.1',
        'device_info': {'model': 'CE5880', 'version': 'VRP-8.180'},
        'evidence': [
            {'config_snippet': 'acl number 3000\n  rule 5 permit ip source 10.1.0.0 0.0.255.255\n# 但 rule-id 写错或反掩码错\npolicy-based-route PBR1\n  node 10 permit\n    if-match acl 3000\n    apply ip-address next-hop 192.168.10.1'},
            {'log_lines': ['traffic-statistics PBR1: packet match 0', 'policy-rule 生效但匹配数 0']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'ACL rule-id 错配或反掩码错（10.1.0.0/16 应配反掩码 0.0.255.255）', 'probability': 0.65,
             'evidence': ['traffic match 0', 'ACL 5 反而被配 0.255.255.255'],
             'verify': 'display acl 3000\ndisplay traffic-policy PBR1',
             'fix': 'acl number 3000\n  rule 10 permit ip source 10.1.0.0 0.0.255.255  # rule-id 10 + 正确反掩码\ninterface 10GE1/0/1\n  traffic-policy PBR1 inbound',
             'rollback': 'undo rule 10'},
            {'rank': 2, 'cause': 'policy-based-route 没应用到入接口', 'probability': 0.2,
             'verify': 'display traffic-policy applied-record',
             'fix': 'interface 10GE1/0/1 → traffic-policy PBR1 inbound'},
            {'rank': 3, 'cause': 'node-id 错配导致不命中', 'probability': 0.15,
             'verify': 'display policy-based-route',
             'fix': 'node 10 改为 node 5 优先'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://support.huawei.com/vrp-pbr', 'version': 'VRP-8.180'}],
    },
    'anti_examples': ['请重启', '删除策略', '改 default 路由'],
    'grading_rubric': {
        'must_have': ['诊断 ACL 错配', '规则反掩码 + rule-id 修正'],
        'nice_to_have': ['traffic-policy inbound 应用'],
        'penalty': ['重启'],
    },
})

# Q-0057 Eth-Trunk LACP Cisco
save({
    'id': 'NSG-Q-0057', 'title': 'Eth-channel 反复 Up/Down（思科 IOS-XE 17，LACP 模式错配）',
    'category': 'troubleshoot', 'vendor': 'cisco', 'version': 'IOS-XE-17.09', 'difficulty': 3,
    'tags': ['eth-channel', 'lacp', 'mode-mismatch'],
    'input': {
        'symptom': 'port-channel 反复 Up/Down；show etherchannel summary 显示 "P/"',
        'device_info': {'model': 'Catalyst 9500-40Y4C', 'version': 'IOS-XE 17.09.04a'},
        'evidence': [
            {'config_snippet': '# Switch-A\ninterface range g1/0/1-2\n  channel-group 10 mode active\n# Switch-B\ninterface range g1/0/1-2\n  channel-group 10 mode on   # ⚠️ on vs active 模式不匹配'},
            {'log_lines': ['show etherchannel 10 summary: (P/)', 'p2p lacp 失败 收到 (S)']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'LACP 模式不一致（active vs on）', 'probability': 0.7,
             'evidence': ['show etherchannel summary 显示 (P/) 端口个别属于'],
             'verify': 'show etherchannel summary\nshow etherchannel 10 detail',
             'fix': 'interface range g1/0/1-2\n  channel-group 10 mode active  # Switch-B 也改 active',
             'rollback': 'channel-group 10 mode on'},
            {'rank': 2, 'cause': 'STP block 导致', 'probability': 0.2,
             'verify': 'show spanning-tree detail',
             'fix': 'spanning-tree portfast trunk in port-channel'},
            {'rank': 3, 'cause': 'speed/duplex 错配', 'probability': 0.1,
             'verify': 'show interface status',
             'fix': '两侧 speed duplex 强制一致'},
        ],
        'references': [{'type': 'rfc', 'url': 'https://datatracker.ietf.org/doc/html/rfc7796', 'title': 'LACPDU'}],
    },
    'anti_examples': ['请重启', '关闭 eth-channel', '强制 on 模式两台'],
    'grading_rubric': {
        'must_have': ['诊断 active vs on 模式错配', '修复统一 active'],
        'nice_to_have': ['RFC 7796 引用'],
        'penalty': ['重启'],
    },
})

# Q-0058 VXLAN ARP suppress missing Cisco
save({
    'id': 'NSG-Q-0058', 'title': 'VXLAN ARP 表振荡（思科 NX-OS 9.3，ARP suppression 配置不一致）',
    'category': 'troubleshoot', 'vendor': 'cisco', 'version': 'NX-OS-9.3', 'difficulty': 4,
    'tags': ['vxlan', 'arp', 'suppression'],
    'input': {
        'symptom': 'Type-2 路由正常但 ARP 表频繁变化',
        'device_info': {'model': 'Nexus 9336C-FX2', 'version': 'NX-OS 9.3(8)'},
        'evidence': [
            {'config_snippet': '# Leaf-A\nl2vpn evpn instance 10 point-to-point\n  arp suppress  # 启用\n# Leaf-B\nl2vpn evpn instance 10 point-to-point\n  ! ⚠️ 未启用 arp suppress'},
            {'log_lines': ['show ip arp suppression-cache Leaf-A: 100 entries', 'Leaf-B: empty']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'ARP suppression 配置不一致（部分 Leaf 启用）', 'probability': 0.7,
             'evidence': ['Leaf-A enabled 100 ARP, Leaf-B 0 ARP'],
             'verify': 'show ip arp suppression-cache\nshow l2vpn evpn instance detail',
             'fix': 'l2vpn evpn instance 10 point-to-point\n  arp suppress\n# Leaf-B 端也加',
             'rollback': 'no arp suppress'},
            {'rank': 2, 'cause': 'VTEP gateway IP 配错', 'probability': 0.15,
             'verify': 'show nve peer',
             'fix': '检查 anycast gateway 一致性'},
            {'rank': 3, 'cause': 'BGP RR 不通告 Type-2 路由', 'probability': 0.15,
             'verify': 'show bgp l2vpn evpn type-2',
             'fix': '检查 RT 与 redistribute'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://www.cisco.com/c/en/us/td/docs/switches/datacenter/sw/nx-os/vxlan/arp-suppress', 'version': 'NX-OS-9.3'}],
    },
    'anti_examples': ['请重启', '关闭 EVPN', '禁 Type-2'],
    'grading_rubric': {
        'must_have': ['诊断 ARP suppression 不一致', '两 Leaf 一致启用'],
        'nice_to_have': ['VTEP gateway 配置'],
        'penalty': ['重启'],
    },
})

# Q-0059 IPsec PAS Cisco
save({
    'id': 'NSG-Q-0059', 'title': 'IPsec 加密流量 NAT 协商失败（思科 IOS-XE 17，UDP 4500 未放行）',
    'category': 'troubleshoot', 'vendor': 'cisco', 'version': 'IOS-XE-17.09', 'difficulty': 4,
    'tags': ['ipsec', 'nat-traversal', 'udp-4500'],
    'input': {
        'symptom': 'IPsec 隧道 UP 但流量不通',
        'device_info': {'model': 'ISR 4451-X', 'version': 'IOS-XE 17.09.04a'},
        'evidence': [
            {'config_snippet': 'crypto ipsec transform-set TSET esp-aes 256\ncrypto map CMAP 10 ipsec-isakmp\n  set peer 198.51.100.1\n# NAT 在 transport 边界'},
            {'log_lines': ['%CRYPTO-5-IKE_PHASE2_DOWN: Phase-2 down', 'NAT keepalive timeout']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'NAT 边界放行了 UDP 500 但未放行 UDP 4500', 'probability': 0.6,
             'evidence': ['NAT keepalive timeout'],
             'verify': 'show crypto ipsec sa\nshow ip access-list',
             'fix': '# 在 NAT 边界设备上\nip access-list extended ACL-NAT\n  permit udp any eq 4500 any eq 4500\n  permit esp any any\n# ISR 上启用 nat-trans\ncrypto isakmp nat-traversal 10000',
             'rollback': 'undo ip access-list ACL-NAT'},
            {'rank': 2, 'cause': 'IPsec 加密流量 ASP 丢', 'probability': 0.25,
             'verify': 'show crypto isakmp count',
             'fix': '分段 MP'},
            {'rank': 3, 'cause': 'QoS 限制 ESP 流量', 'probability': 0.15,
             'verify': 'show policy-map',
             'fix': '提升 ESP 优先级'},
        ],
        'references': [{'type': 'rfc', 'url': 'https://datatracker.ietf.org/doc/html/rfc3947', 'title': 'Negotiation of NAT-Traversal in IKE'}],
    },
    'anti_examples': ['请重启', '禁用 IPsec', '关 NAT'],
    'grading_rubric': {
        'must_have': ['诊断 NAT-T UDP 4500', 'firewall 放行'],
        'nice_to_have': ['nat-traversal 启用'],
        'penalty': ['关 IPsec'],
    },
})

# Q-0060 VRRP 切换 Junos
save({
    'id': 'NSG-Q-0060', 'title': 'VRRP 频繁主备切换（Juniper 21.2，preempt 配置错配）',
    'category': 'troubleshoot', 'vendor': 'juniper', 'version': '21.2R1', 'difficulty': 3,
    'tags': ['vrrp', 'high-availability', 'preempt'],
    'input': {
        'symptom': 'VRRP 频繁切换（5 分钟/次）',
        'device_info': {'model': 'MX204', 'version': 'Junos 21.2R1.6'},
        'evidence': [
            {'config_snippet': '# Device-A\nset interfaces ge-0/0/1 unit 0 family inet address 10.1.1.2/24 vrrp-group 1 virtual-address 10.1.1.1 priority 110\n# Device-B\nset interfaces ge-0/0/1 unit 0 family inet address 10.1.1.3/24 vrrp-group 1 virtual-address 10.1.1.1 priority 100\n# ⚠️ A 没配 preempt，B 是默认 preempt'},
            {'log_lines': ['show vrrp detail: state frequent Flip']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'B 抢占 (preempt) 开启，但 B priority 低', 'probability': 0.5,
             'evidence': ['B 每次重连都触发抢占'],
             'verify': 'show vrrp detail',
             'fix': '# 关闭 B 的 preempt\nset interfaces ge-0/0/1 unit 0 family inet vrrp-group 1 no-preempt',
             'rollback': 'delete interfaces ge-0/0/1 unit 0 family inet vrrp-group 1 no-preempt'},
            {'rank': 2, 'cause': 'priority 反了或接口 down', 'probability': 0.3,
             'verify': 'show interfaces ge-0/0/1',
             'fix': '恢复 interface + 改 priority'},
            {'rank': 3, 'cause': 'BFD 抖动', 'probability': 0.2,
             'verify': 'show bfd session',
             'fix': '调慢 BFD interval'},
        ],
        'references': [{'type': 'rfc', 'url': 'https://datatracker.ietf.org/doc/html/rfc5798', 'title': 'VRRPv3 for IPv4/IPv6'}],
    },
    'anti_examples': ['请重启', '改 priority 1', '关 VRRP'],
    'grading_rubric': {
        'must_have': ['诊断 preempt 开启', '关闭 B preempt'],
        'nice_to_have': ['BFD interval'],
        'penalty': ['重启'],
    },
})

# Q-0061 IPv6 default route Juniper
save({
    'id': 'NSG-Q-0061', 'title': 'IPv6 默认路由丢失（Juniper 21.2，ndp/dhcpv6 中继配错）',
    'category': 'troubleshoot', 'vendor': 'juniper', 'version': '21.2R1', 'difficulty': 3,
    'tags': ['ipv6', 'default-route', 'ndp', 'dhcpv6'],
    'input': {
        'symptom': 'IPv6 默认路由 2000::/3 缺失',
        'device_info': {'model': 'MX204', 'version': 'Junos 21.2R1.6'},
        'evidence': [
            {'config_snippet': 'set routing-options rib inet6.0 static route ::/0 next-hop 2001:db8::1\n# ⚠️ 缺 interface route aggregation'},
            {'log_lines': ['show route ::/0: not found']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': '下一跳 2001:db8::1 不可达 / 不在 IGP 上通告', 'probability': 0.6,
             'evidence': ['route not found'],
             'verify': 'show route 2001:db8::1',
             'fix': 'set routing-options rib inet6.0 static route ::/0 qualified-next-hop 2001:db8::1 interface ge-0/0/1.0',
             'rollback': 'delete routing-options static route ::/0'},
            {'rank': 2, 'cause': 'IPv6 路由协议未开启（routing-options inet6 disabled）', 'probability': 0.2,
             'verify': 'show ipv6 forwarding',
             'fix': 'set forwarding-options family inet6 route-monitoring'},
            {'rank': 3, 'cause': 'Neighbor cache 失效', 'probability': 0.2,
             'verify': 'show ipv6 neighbor',
             'fix': 'clear ipv6 neighbor'},
        ],
        'references': [{'type': 'rfc', 'url': 'https://datatracker.ietf.org/doc/html/rfc4861', 'title': 'Neighbor Discovery for IPv6'}],
    },
    'anti_examples': ['请重启', '关 IPv6 routing', '改 default route 静默'],
    'grading_rubric': {
        'must_have': ['诊断下一跳不可达', 'qualified-next-hop'],
        'nice_to_have': ['route-monitoring 开启'],
        'penalty': ['关闭 IPv6'],
    },
})

# Q-0062 H3C Stacking
save({
    'id': 'NSG-Q-0062', 'title': 'H3C IRF 分裂事件（Comware 7.1，MAD 检测选举冲突）',
    'category': 'troubleshoot', 'vendor': 'h3c', 'version': 'Comware-7.1.070', 'difficulty': 5,
    'tags': ['irf', 'split', 'mad', 'conflicts'],
    'input': {
        'symptom': 'IRF 反复 split 后两台设备都被选举为 Master',
        'device_info': {'model': 'S12504X-AF', 'version': 'Comware 7.1.070 R7625'},
        'evidence': [
            {'config_snippet': '# Device-A\nirf member 1 priority 32\nmad detection-mode arp\n# Device-B\nirf member 2 priority 32  # 同优先级冲突'},
            {'log_lines': ['%20IRF/5/IRF_SPLIT: IRF system split into two', '%20IRF/4/MAD_CONFLICT:']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': '两端 IRF priority 同分冲突，MAD 协议也未决高下', 'probability': 0.6,
             'evidence': ['MAD_CONFLICT log'],
             'verify': 'display irf\ndisplay mad verbose',
             'fix': '# Device-A: priority 32 保持\n# Device-B: 改 priority 16\nirf member 2 priority 16\n# 改 MAD 检测\nmad detection-mode lldp  # 比 arp 更精确',
             'rollback': 'undo irf member 2 priority'},
            {'rank': 2, 'cause': 'MAD 接口本身 down 导致 false positive', 'probability': 0.25,
             'verify': 'display mad interface',
             'fix': '检查 MAD 接口状态'},
            {'rank': 3, 'cause': 'IRF link 上行设备未配置 IRF-helper', 'probability': 0.15,
             'verify': 'show irf topology',
             'fix': '在 transit 设备上配 irf helper'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://www.h3c.com/cn/d_202206/irf-mad', 'version': 'Comware 7.1.070'}],
    },
    'anti_examples': ['请重启', '关闭 IRF', '改 stacking 模式'],
    'grading_rubric': {
        'must_have': ['诊断 priority 冲突', '修复 priority 分级'],
        'nice_to_have': ['MAD 检测模式选择'],
        'penalty': ['关闭 IRF'],
    },
})

# Q-0063 static_route preference Arista
save({
    'id': 'NSG-Q-0063', 'title': '浮动静态路由不切换（Arista EOS 4.24，preference 设错）',
    'category': 'troubleshoot', 'vendor': 'arista', 'version': '4.24', 'difficulty': 3,
    'tags': ['static-route', 'float', 'preference'],
    'input': {
        'symptom': '主路由 down 后 floating route 未接管',
        'device_info': {'model': 'DCS-7280QR-C36', 'version': 'EOS 4.24.6M'},
        'evidence': [
            {'config_snippet': 'ip route 0.0.0.0/0 10.1.1.1\nip route 0.0.0.0/0 192.168.1.1 254  # ⚠️ AD=254 太高'},
            {'log_lines': ['show ip route 0.0.0.0/0: via 10.1.1.1 unreachable but still active']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'floating route preference 254 太高（应低于默认 1）', 'probability': 0.7,
             'evidence': ['default route AD 254'],
             'verify': 'show ip route 0.0.0.0/0',
             'fix': 'ip route 0.0.0.0/0 192.168.1.1 100  # 100 < 默认 1 的浮动路由',
             'rollback': 'no ip route 0.0.0.0/0 192.168.1.1'},
            {'rank': 2, 'cause': '主路由 link-probe 探测发现 up（虚假）', 'probability': 0.2,
             'verify': 'show interface | include down\nip sla',
             'fix': 'track 真实可达性'},
            {'rank': 3, 'cause': 'ECMP 设错', 'probability': 0.1,
             'verify': 'show ip route summary',
             'fix': 'no ecmp → 自动 fallback'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://www.arista.com/en/docs/eos-4.24/static-route', 'version': 'EOS 4.24'}],
    },
    'anti_examples': ['请重启', '删除全部静态路由', '改 IGW'],
    'grading_rubric': {
        'must_have': ['诊断 preference 设错', '修复 AD 值'],
        'nice_to_have': ['track 监测'],
        'penalty': ['重启'],
    },
})

# Q-0064 IPv4 ACL miss
save({
    'id': 'NSG-Q-0064', 'title': 'IPv4 ACL 包统计为 0（华为 VRP-8.180，traffic-filter 应用方向错）',
    'category': 'troubleshoot', 'vendor': 'huawei', 'version': 'VRP-8.180', 'difficulty': 2,
    'tags': ['acl', 'packet-filter', 'traffic-statistics'],
    'input': {
        'symptom': 'ACL 匹配数为 0，但流量实际全通',
        'device_info': {'model': 'CE5880', 'version': 'VRP-8.180'},
        'evidence': [
            {'config_snippet': 'acl 3000\n  rule 10 deny ip source 192.168.1.0 0.0.0.255\n# 应 apply 在入接口\ninterface 10GE1/0/1\n  traffic-filter outbound acl 3000  # ⚠️ 这里是源 IP 应用 outbound 错方向'},
            {'log_lines': ['display traffic-filter applied-record: hits 0']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'traffic-filter outbound 配错方向（应 inbound 匹配 source）', 'probability': 0.7,
             'evidence': ['hits 0'],
             'verify': 'display acl 3000\ndisplay traffic-filter applied-record',
             'fix': 'interface 10GE1/0/1\n  undo traffic-filter outbound acl 3000\n  traffic-filter inbound acl 3000',
             'rollback': 'undo traffic-filter inbound'},
            {'rank': 2, 'cause': 'ACL rule 反掩码错', 'probability': 0.2,
             'verify': 'display acl 3000',
             'fix': 'acl 3000\n  rule 10 deny ip source 192.168.1.0 0.0.0.255'},
            {'rank': 3, 'cause': '其他位置已 permit', 'probability': 0.1,
             'verify': 'display acl 3000',
             'fix': '在 rule 10 后加更精细规则'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://support.huawei.com/vrp-acl', 'version': 'VRP-8.180'}],
    },
    'anti_examples': ['请重启', '删除 ACL', '关闭接口'],
    'grading_rubric': {
        'must_have': ['诊断方向错（outbound）', '修复 inbound'],
        'nice_to_have': ['反掩码检查'],
        'penalty': ['重启'],
    },
})

# Q-0065 SNMP trap Cisco
save({
    'id': 'NSG-Q-0065', 'title': 'SNMP trap 收不到（思科 IOS-XE 17，trap-source 配错）',
    'category': 'troubleshoot', 'vendor': 'cisco', 'version': 'IOS-XE-17.09', 'difficulty': 3,
    'tags': ['snmp', 'trap', 'trap-source'],
    'input': {
        'symptom': 'NMS 收不到链路 flap 的 trap，但 snmpwalk 能返回数据',
        'device_info': {'model': 'ASR 1001-X', 'version': 'IOS-XE 17.09.04a'},
        'evidence': [
            {'config_snippet': 'snmp-server host 10.1.1.100 traps public udp-port 162\nsnmp-server trap-source Loopback0  # ⚠️ 实际 NMS 接收不到 source IP 不可达的包\nsnmp-server community public RO'},
            {'log_lines': ['debug snmp packet: 收到 ICMP unreachable from 10.0.0.1 for source Loopback0']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'trap-source Loopback0 不可达或 ACL 阻断', 'probability': 0.6,
             'evidence': ['NMS 端收到 ICMP unreachable for source'],
             'verify': 'ping 10.0.0.1 source Loopback0\nshow snmp traps',
             'fix': '# 改 trap-source 到一个 NMS 直连接口\nno snmp-server trap-source Loopback0\nsnmp-server trap-source Vlan100\n# 同时 ACL 放行 UDP/162',
             'rollback': 'no snmp-server trap-source Vlan100'},
            {'rank': 2, 'cause': 'snmp-server host 是 traps 但用了 RO community', 'probability': 0.25,
             'verify': 'show snmp host',
             'fix': 'snmp-server host 10.1.1.100 traps NetSys@2024'},
            {'rank': 3, 'cause': 'UDP/162 ACL 中间阻断', 'probability': 0.15,
             'verify': 'show ip access-list | include 162',
             'fix': 'permit udp host x.x.x.x eq snmptrap any'},
        ],
        'references': [{'type': 'rfc', 'url': 'https://datatracker.ietf.org/doc/html/rfc3418', 'title': 'SNMP MIB'}],
    },
    'anti_examples': ['请重启', '改 RO community', '关 snmp-server'],
    'grading_rubric': {
        'must_have': ['诊断 trap-source 不可达', '改用直连接口'],
        'nice_to_have': ['ACL 放行'],
        'penalty': ['重启'],
    },
})

# Q-0066 NS 故障
save({
    'id': 'NSG-Q-0066', 'title': 'Huawei CloudEngine NX-OS ospf 类型 P2MP 学习不到下游路由',
    'category': 'troubleshoot', 'vendor': 'huawei', 'version': 'VRP-8.180', 'difficulty': 4,
    'tags': ['ospf', 'p2mp', 'network-type'],
    'input': {
        'symptom': 'OSPF P2MP Hub-Spoke 下游路由学习不到',
        'device_info': {'model': 'CE5855-EI', 'version': 'VRP-8.180'},
        'evidence': [
            {'config_snippet': '# Hub\ninterface 10GE1/0/1\n  ospf network-type p2mp\n  ospf p2mp neighbor 10.1.1.1\n# Spoke 端 network-type 是 broadcast'},
            {'log_lines': ['display ospf lsdb: 缺少 Type-3']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'P2MP Hub 与 Spoke 端 network-type 不一致', 'probability': 0.7,
             'evidence': ['Type-3 缺失'],
             'verify': 'display ospf interface 10GE1/0/1 | include Network',
             'fix': '# Spoke 端\ninterface 10GE1/0/1\n  ospf network-type p2mp\n  ospf p2mp neighbor 10.1.1.2  # back to Hub',
             'rollback': 'undo ospf network-type'},
            {'rank': 2, 'cause': 'P2MP 邻居命令格式错', 'probability': 0.2,
             'verify': 'display ospf p2mp neighbor',
             'fix': 'ospf p2mp neighbor <ip> p2mp-type broadcast'},
            {'rank': 3, 'cause': 'NBMA DR 选举不匹配', 'probability': 0.1,
             'verify': 'display ospf neighbor',
             'fix': 'ospf dr-priority 一致'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://support.huawei.com/vrp-ospf-p2mp', 'version': 'VRP-8.180'}],
    },
    'anti_examples': ['请重启', '改 broadcast', '删除 OSPF'],
    'grading_rubric': {
        'must_have': ['诊断 P2MP 类型不一致', '修复 Spoke 端配 p2mp'],
        'nice_to_have': ['p2mp neighbor 命令'],
        'penalty': ['重启'],
    },
})

# Q-0067 IS-IS H3C
save({
    'id': 'NSG-Q-0067', 'title': 'IS-IS 邻居震荡（华三 Comware 7，L1/L2 level mismatch）',
    'category': 'troubleshoot', 'vendor': 'h3c', 'version': 'Comware-7.1.070', 'difficulty': 4,
    'tags': ['isis', 'level-mismatch'],
    'input': {
        'symptom': 'IS-IS 邻居反复 Up/Down，display isis neighbor 显示一直 Init',
        'device_info': {'model': 'S9850-32B', 'version': 'Comware 7.1.070 R7625'},
        'evidence': [
            {'config_snippet': '# Spoke-A\nisis 1\n  is-level level-1\n  network-entity 49.0001.0000.0000.0001.00\n# Spoke-B\nisis 1\n  is-level level-1-2  # ⚠️ L1 vs L1-2 错配'},
            {'log_lines': ['%ISIS-3-LEVEL_MISMATCH: Level mismatch with IS']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'IS-IS level 不一致（L1 vs L1-2）', 'probability': 0.7,
             'evidence': ['ISIS-3-LEVEL_MISMATCH'],
             'verify': 'display isis interface\ndisplay isis peer',
             'fix': '# 统一 level\nisis 1\n  is-level level-1-2',
             'rollback': 'undo is-level'},
            {'rank': 2, 'cause': 'NET address area-id 不一致', 'probability': 0.2,
             'verify': 'display isis',
             'fix': '检查 NET format 一致'},
            {'rank': 3, 'cause': 'IS-IS 认证密码', 'probability': 0.1,
             'verify': 'display isis interface authentication',
             'fix': '统一 domain-password'},
        ],
        'references': [{'type': 'vendor_doc', 'url': 'https://www.h3c.com/cn/d_202206/isis-level', 'version': 'Comware 7.1.070'}],
    },
    'anti_examples': ['请重启', '关闭 IS-IS', '改成 OSPF'],
    'grading_rubric': {
        'must_have': ['诊断 level mismatch', '统一 L1-2'],
        'nice_to_have': ['NET area-id 检查'],
        'penalty': ['重启'],
    },
})

# Q-0068 IPv6 邻居表
save({
    'id': 'NSG-Q-0068', 'title': 'IPv6 邻居 cache 频繁失效（Cisco IOS-XE 17，ND timer 抖动）',
    'category': 'troubleshoot', 'vendor': 'cisco', 'version': 'IOS-XE-17.09', 'difficulty': 3,
    'tags': ['ipv6', 'nd', 'neighbor-cache'],
    'input': {
        'symptom': 'show ipv6 neighbors 频繁变化（incomplete 占比高）',
        'device_info': {'model': 'ASR 1001-X', 'version': 'IOS-XE 17.09.04a'},
        'evidence': [
            {'config_snippet': '# interface 配置 RS 频繁\nipv6 nd cache expire 60  # ⚠️ 太短'},
            {'log_lines': ['show ipv6 neighbors: state=incomplete 30%']},
        ],
        'question': '诊断 + 修复',
    },
    'expected_output': {
        'root_causes': [
            {'rank': 1, 'cause': 'ipv6 nd cache expire 设太短（60s）', 'probability': 0.65,
             'evidence': ['incomplete state 高'],
             'verify': 'show ipv6 interface g1/0/24 | include expire',
             'fix': 'interface g1/0/24\n  ipv6 nd cache expire 14400  # 4 小时更稳',
             'rollback': 'no ipv6 nd cache expire'},
            {'rank': 2, 'cause': '链路质量差', 'probability': 0.25,
             'verify': 'show interface | include CRC',
             'fix': '更换光模块 / 物理链路'},
            {'rank': 3, 'cause': 'ND PREFIX 缺失', 'probability': 0.1,
             'verify': 'show ipv6 interface | include RA',
             'fix': 'ipv6 nd prefix-advertisement 2001:db8::/64 24000 12000'},
        ],
        'references': [{'type': 'rfc', 'url': 'https://datatracker.ietf.org/doc/html/rfc4861', 'title': 'ND'}],
    },
    'anti_examples': ['请重启', '关 IPv6 routing', 'disable neighbors cache'],
    'grading_rubric': {
        'must_have': ['诊断 nd cache expire 短', '修复 14400s'],
        'nice_to_have': ['ND prefix 检查'],
        'penalty': ['关 IPv6'],
    },
})

print('...batch1 全部 35 题完成')
