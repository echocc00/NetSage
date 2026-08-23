"""batch2 config 题骨架生成 - 8 道示范（八种协议 × 代表厂商）。
完整 80 题对应 80 模板，需要更多题可以按此模式扩展。
"""
import yaml, os

OUT = 'eval/dataset'

def save(q):
    p = f'{OUT}/{q["id"]}.yaml'
    yaml.dump(q, open(p, 'w', encoding='utf-8'),
              default_flow_style=False, allow_unicode=True, sort_keys=False, width=240)
    print(f'  wrote {q["id"]}')

# Q-0069 Huawei BGP peering config
save({
    'id': 'NSG-Q-0069',
    'title': '生成华为 CE12800 eBGP 与单 peer 配置',
    'category': 'config',
    'vendor': 'huawei',
    'version': 'VRP-8.180',
    'difficulty': 2,
    'tags': ['bgp', 'ebgp', 'peering'],
    'input': {
        'symptom': '某 Huawei CE12800 与对端 AS 65002 建立 eBGP，对端 IP 10.1.1.2，通告 192.168.0.0/16。本地 AS 65001，router-id 10.0.0.1',
        'device_info': {'model': 'CE12808', 'version': 'VRP-8.180'},
        'question': '生成 eBGP peer 配置',
    },
    'expected_output': {
        'config': (
            'bgp 65001\n'
            ' router-id 10.0.0.1\n'
            ' peer 10.1.1.2 as-number 65002\n'
            ' peer 10.1.1.2 password cipher Huawei@2024\n'
            ' #\n'
            ' ipv4-family unicast\n'
            '  peer 10.1.1.2 enable\n'
            '  network 192.168.0.0 255.255.0.0\n'
        ),
        'references': [{'type': 'vendor_doc', 'url': 'https://support.huawei.com/vrp-bgp', 'version': 'VRP-8.180'}],
    },
    'anti_examples': [
        '漏 router-id',
        '用 ipv4-family 写错缩进（应 2 空格 vs 4 空格）',
        '漏 ipv4-family unicast → peer enable',
    ],
    'grading_rubric': {
        'must_have': ['bgp <asn>', 'router-id', 'peer x.x.x.x as-number', 'ipv4-family unicast peer enable', 'network 通告'],
        'nice_to_have': ['密码认证', 'next-hop-local'],
        'penalty': ['漏 router-id', 'ipv4-family peer 缩进错', 'network 反掩码 vs 掩码使用错'],
    },
})

# Q-0070 Cisco OSPF area config
save({
    'id': 'NSG-Q-0070',
    'title': '生成思科 IOS-XE 17 OSPF area 0 + passive-interface default',
    'category': 'config',
    'vendor': 'cisco',
    'version': 'IOS-XE-17.09',
    'difficulty': 2,
    'tags': ['ospf', 'area-0', 'passive'],
    'input': {
        'symptom': '某 Cisco ASR 1001-X 路由器配 OSPF process 1，router-id 10.0.0.1，所有接口入 area 0。只有 Lo100 应当主动发 Hello。',
        'device_info': {'model': 'ASR 1001-X', 'version': 'IOS-XE 17.09.04a'},
        'question': '生成 OSPF 配置',
    },
    'expected_output': {
        'config': (
            'router ospf 1\n'
            ' router-id 10.0.0.1\n'
            ' passive-interface default\n'
            ' no passive-interface Loopback100\n'
            ' network 10.0.0.0 0.255.255.255 area 0\n'
            ' network 192.168.0.0 0.0.255.255 area 0\n'
        ),
        'references': [{'type': 'vendor_doc', 'url': 'https://www.cisco.com/c/en/us/support/ospf-passive', 'version': 'IOS-XE-17.09'}],
    },
    'anti_examples': [
        '用 wildcard mask 0.0.0.255 错（应 0.0.255.255 for /24）',
        '漏 passive-interface default',
    ],
    'grading_rubric': {
        'must_have': ['router ospf <pid>', 'router-id', 'network <addr> <wildcard> area 0', 'passive-interface default'],
        'nice_to_have': ['no passive-interface Loopback'],
        'penalty': ['wildcard mask 反掩码错', '缺 router-id'],
    },
})

# Q-0071 H3C OSPF stub
save({
    'id': 'NSG-Q-0071',
    'title': '生成华三 S6850 OSPF area 0.0.0.1 stub no-summary',
    'category': 'config',
    'vendor': 'h3c',
    'version': 'Comware-7.1.070',
    'difficulty': 3,
    'tags': ['ospf', 'totally-stub'],
    'input': {
        'symptom': '某 H3C S6850 配 OSPF area 0.0.0.1 为 totally-stub（ABR 上抑制 type-3），进程 1 router-id 10.0.0.1',
        'device_info': {'model': 'S6850-56HF', 'version': 'Comware 7.1.070 R7625'},
        'question': '生成 OSPF totally-stub 配置',
    },
    'expected_output': {
        'config': (
            'ospf 1 router-id 10.0.0.1\n'
            ' #\n'
            ' area 0.0.0.1\n'
            '  stub no-summary\n'
        ),
        'references': [{'type': 'vendor_doc', 'url': 'https://www.h3c.com/cn/d_202206/ospf-totally-stub', 'version': 'Comware 7.1.070'}],
    },
    'anti_examples': [
        '只配 stub 漏 no-summary',
        '把 no-summary 写在 stub 之前',
    ],
    'grading_rubric': {
        'must_have': ['ospf <pid> router-id', 'area 0.0.0.1', 'stub no-summary'],
        'nice_to_have': ['冒号前后空格'],
        'penalty': ['漏 no-summary', '缩进错'],
    },
})

# Q-0072 Huawei BGP route_reflector
save({
    'id': 'NSG-Q-0072',
    'title': '生成华为 NE40E Route Reflector 配置（cluster-id 10.0.0.1）',
    'category': 'config',
    'vendor': 'huawei',
    'version': 'VRP-8.180',
    'difficulty': 3,
    'tags': ['bgp', 'route-reflector', 'cluster-id'],
    'input': {
        'symptom': '某 Huawei NE40E-X16 作为 RR，cluster-id 10.0.0.1，本地 AS 65000，客户端 peer 10.1.1.10（AS 65000）',
        'device_info': {'model': 'NE40E-X16', 'version': 'VRP-8.180'},
        'question': '生成 RR 配置',
    },
    'expected_output': {
        'config': (
            'bgp 65000\n'
            ' router-id 10.0.0.1\n'
            ' #\n'
            ' peer 10.0.0.1 reflect-client     # cluster-id 由 peer 行指定\n'
            ' #\n'
            ' ipv4-family unicast\n'
            '  peer 10.1.1.10 as-number 65000\n'
            '  peer 10.1.1.10 reflect-client\n'
            '  peer 10.1.1.10 next-hop-local\n'
        ),
        'references': [{'type': 'vendor_doc', 'url': 'https://support.huawei.com/vrp-bgp-rr', 'version': 'VRP-8.180'}],
    },
    'anti_examples': [
        '漏 reflector cluster-id',
        '在 client 端也配 reflect-client（错，应在 RR 上）',
        '忘了 next-hop-local',
    ],
    'grading_rubric': {
        'must_have': ['bgp 65000', 'router-id', 'reflect-client', 'ipv4-family'],
        'nice_to_have': ['next-hop-local'],
        'penalty': ['reflect-client 写错端', '漏 cluster-id'],
    },
})

# Q-0073 Cisco VXLAN EVPN
save({
    'id': 'NSG-Q-0073',
    'title': '生成思科 IOS-XE 17 单 Spine EVPN VXLAN L2VNI 10 配置',
    'category': 'config',
    'vendor': 'cisco',
    'version': 'IOS-XE-17.09',
    'difficulty': 4,
    'tags': ['vxlan', 'evpn', 'l2vni', 'bgp'],
    'input': {
        'symptom': '某 Cisco Catalyst 9300 作 Spine，AS 65000，loopback 10.0.0.1。L2VNI 10010 对应 VLAN 10，REDIRECT-DIST 65000:10010，对端 Leaf 10.1.1.1。',
        'device_info': {'model': 'Catalyst 9300-48P', 'version': 'IOS-XE 17.09.04a'},
        'question': '生成 VXLAN EVPN Spine + L2VNI 配置',
    },
    'expected_output': {
        'config': (
            'nv overlay evpn\n'
            'feature vn-segment-vlan-based\n'
            'feature nv overlay\n'
            '!\n'
            'l2vpn evpn\n'
            ' replication-type static\n'
            ' router-id Loopback0\n'
            '!\n'
            'vlan 10\n'
            ' vn-segment 10010\n'
            '!\n'
            'router bgp 65000\n'
            ' address-family l2vpn evpn\n'
            '  neighbor 10.1.1.1 activate\n'
            '  neighbor 10.1.1.1 send-community both\n'
            '!\n'
            ' l2vpn evpn instance 10 point-to-point\n'
            '  rd 10.0.0.1:10\n'
            '  route-target import 65000:10010\n'
            '  route-target export 65000:10010\n'
        ),
        'references': [{'type': 'vendor_doc', 'url': 'https://www.cisco.com/c/en/us/support/nx-os-9.3-vxlan-evpn', 'version': 'IOS-XE-17.09'}],
    },
    'anti_examples': [
        '忘 nv overlay evpn 全局开启',
        'RD/RT 拼写错',
        'address-family l2vpn evpn 漏 activate',
    ],
    'grading_rubric': {
        'must_have': ['nv overlay evpn', 'l2vpn evpn', 'vni 10010', 'rd 配置', 'route-target', 'BGP address-family activate'],
        'nice_to_have': ['vn-segment 命名规范'],
        'penalty': ['漏 nv overlay', 'RD/RT 错误'],
    },
})

# Q-0074 Juniper static-route default
save({
    'id': 'NSG-Q-0074',
    'title': '生成 Juniper EX4300 IPv6 默认路由（next-hop 2001:db8::1）',
    'category': 'config',
    'vendor': 'juniper',
    'version': '21.2R1',
    'difficulty': 2,
    'tags': ['static-route', 'ipv6', 'default'],
    'input': {
        'symptom': '某 Juniper EX4300 配 IPv6 默认路由，下一跳 2001:db8::1',
        'device_info': {'model': 'EX4300-48T', 'version': 'Junos 21.2R1.6'},
        'question': '生成 IPv6 默认路由',
    },
    'expected_output': {
        'config': (
            'set routing-options rib inet6.0 static route ::/0 next-hop 2001:db8::1\n'
        ),
        'references': [{'type': 'vendor_doc', 'url': 'https://www.juniper.net/documentation/junos-21.2/static-route-ipv6', 'version': '21.2R1'}],
    },
    'anti_examples': [
        '漏 rib inet6.0（IPv6 路由表）',
        '用 set routing-options static route 0/0 (IPv4 syntax)',
    ],
    'grading_rubric': {
        'must_have': ['routing-options rib inet6.0', 'static route ::/0', 'next-hop 2001:db8::1'],
        'nice_to_have': ['qualified-next-hop 接口'],
        'penalty': ['写成 IPv4 syntax'],
    },
})

# Q-0075 Arista vxlan anycast
save({
    'id': 'NSG-Q-0075',
    'title': '生成 Arista EOS 4.24 单 Leaf VXLAN EVPN anycast-gateway MAC 00:00:5e:00:01:20',
    'category': 'config',
    'vendor': 'arista',
    'version': '4.24',
    'difficulty': 4,
    'tags': ['vxlan', 'evpn', 'anycast-gateway'],
    'input': {
        'symptom': '某 Arista DCS-7280 配 VNI 10020 anycast-gateway，VR MAC 00:00:5e:00:01:20，对端 leaf BGP peer 10.1.1.10',
        'device_info': {'model': 'DCS-7280QR-C36', 'version': 'EOS 4.24.6M'},
        'question': '生成 Arista VXLAN anycast-gateway 配置',
    },
    'expected_output': {
        'config': (
            'ip virtual-router mac-address 00:00:5e:00:01:20\n'
            '!\n'
            'vlan 20\n'
            ' vn-segment 10020\n'
            '!\n'
            'interface Vxlan1\n'
            ' vxlan vlan 20 vni 10020\n'
            '!\n'
            'interface Vlan20\n'
            ' ip address 10.1.20.1/24\n'
            ' ip virtual-router address 10.1.20.1\n'
            '!\n'
            'router bgp 65000\n'
            ' address-family evpn\n'
            '  neighbor 10.1.1.10 activate\n'
        ),
        'references': [{'type': 'vendor_doc', 'url': 'https://www.arista.com/en/docs/eos-4.24/evpn-vxlan', 'version': 'EOS 4.24'}],
    },
    'anti_examples': [
        '忘 ip virtual-router mac-address',
        'Vxlan1 没绑 vlan',
    ],
    'grading_rubric': {
        'must_have': ['ip virtual-router mac-address', 'vni 配置', 'BGP evpn 邻居'],
        'nice_to_have': ['mac 格式规范'],
        'penalty': ['缺 anycast-gateway 全局', 'BGP 邻居 漏 activate'],
    },
})

# Q-0076 Huawei ipsec_site2site
save({
    'id': 'NSG-Q-0076',
    'title': '生成华为 USG IPsec site-to-site 配置（AES256+SHA256）',
    'category': 'config',
    'vendor': 'huawei',
    'version': 'VRP-8.180',
    'difficulty': 4,
    'tags': ['ipsec', 'site-to-site', 'ikev1'],
    'input': {
        'symptom': '某 Huawei USG 6680 与对端 10.1.2.1 建 IPsec 隧道（pre-share-key "NetSys@2024"），保护 10.0.1.0/24 ↔ 10.0.2.0/24',
        'device_info': {'model': 'USG 6680', 'version': 'VRP-8.180'},
        'question': '生成 IPsec site-to-site 配置',
    },
    'expected_output': {
        'config': (
            'ike proposal 1\n'
            ' encryption-algorithm aes-cbc-256\n'
            ' authentication-algorithm pre-share\n'
            ' integrity-algorithm sha2-256\n'
            ' dh group14\n'
            '#\n'
            'ike peer peer1\n'
            ' pre-shared-key cipher NetSys@2024\n'
            ' remote-address 10.1.2.1\n'
            ' ike-proposal 1\n'
            '#\n'
            'ipsec proposal prop1\n'
            ' encapsulation-mode tunnel\n'
            ' esp authentication-algorithm sha2-256\n'
            ' esp encryption-algorithm aes-cbc-256\n'
            '#\n'
            'ipsec policy pol1 1 isakmp\n'
            ' security acl 3000\n'
            ' ike-peer peer1\n'
            ' proposal prop1\n'
            '#\n'
            'acl 3000\n'
            ' rule 5 permit ip source 10.0.1.0 0.0.0.255 destination 10.0.2.0 0.0.0.255\n'
            '#\n'
            'interface 10GE1/0/1\n'
            ' ip address 198.51.100.1 255.255.255.0\n'
            ' ipsec policy pol1\n'
            '#\n'
            'ip route-static 10.0.2.0 255.255.255.0 198.51.100.254\n'
        ),
        'references': [{'type': 'vendor_doc', 'url': 'https://support.huawei.com/vrp-ipsec-site2site', 'version': 'VRP-8.180'}],
    },
    'anti_examples': [
        '漏 acl 感兴趣流',
        'proposal esp 与 ike proposal 名称冲突',
        '忘了应用 ipsec policy 在接口上',
    ],
    'grading_rubric': {
        'must_have': ['ike proposal', 'ike peer', 'ipsec proposal', 'ipsec policy isakmp', 'acl 感兴趣流', '接口应用', 'static-route'],
        'nice_to_have': ['DH group 14 一致', 'pre-shared-key'],
        'penalty': ['漏 acl', '漏接口应用', 'algo 与对端不一'],
    },
})

print('...8 config done')
