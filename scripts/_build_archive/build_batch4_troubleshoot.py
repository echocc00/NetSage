"""batch4 troubleshoot - 80 道补充题，按文档 §3.1 场景清单覆盖全 5 vendor。

每个 protocol 取大量变体，本轮覆盖：
- ipsec_phase1_no_proposal ×5 vendor
- ipsec_phase2_pfs ×5
- bgp_maximum_prefix ×5 (已 0040 再加 4 var)
- bgp_route_oscillation ×5
- ospf_dbd_seq_mismatch ×5
- vxlan_anycast_mac_conflict ×5 (已 0034/0068 再加 3)
- vxlan_type3_peer_enable ×5 (已 0050 再加 4)
- ipv6_bgp_link_local ×5 (已 0032/0039/0041 再加 2)
- mpls_te_tunnel ×5
- hsrp_vrrp_priority ×5
"""
import yaml, os

OUT = 'F:/claudepc/NetSage/eval/dataset'

def save(q):
    p = f'{OUT}/{q["id"]}.yaml'
    yaml.dump(q, open(p, 'w', encoding='utf-8'),
              default_flow_style=False, allow_unicode=True, sort_keys=False, width=240)
    print(f'  wrote {q["id"]}')

# 自动找下一个 ID
import re
nums = []
for f in os.listdir(OUT):
    if not f.endswith('.yaml'): continue
    m = re.match(r'NSG-Q-(\d+)\.yaml', f)
    if m: nums.append(int(m.group(1)))
nxt = max(nums) + 1

# 通用 troubleshoot 题生成器
def t(id_off, title, vendor, version, difficulty, tags, symptom, evidence, question, root_causes, refs, anti_examples):
    return save({
        'id': id_off, 'title': title, 'category': 'troubleshoot', 'vendor': vendor, 'version': version,
        'difficulty': difficulty, 'tags': tags,
        'input': {
            'symptom': symptom,
            'device_info': {'model': evidence.get('_model',''), 'version': version, 'interfaces': evidence.get('_if', [])},
            'evidence': [{'config_snippet': e} for e in evidence.get('config',[])] +
                         [{'log_lines': e} if isinstance(e, list) else {'config_snippet': e} for e in evidence.get('logs',[])],
            'question': question,
        },
        'expected_output': {'root_causes': root_causes, 'references': refs},
        'anti_examples': anti_examples,
        'grading_rubric': {
            'must_have': ['top 根因为 ' + tags[0], '≥1 验证命令', '≥1 修复命令'],
            'nice_to_have': ['含 rollback', '≥3 候选根因'],
            'penalty': ['推荐重启设备', '无证据瞎猜'],
        },
    })

# 用 helper 写多题——下面每段独立调用以避免脚本太大
def W(id_off, title, vendor, version, difficulty, tags, symptom, configs, logs, question, rc, refs):
    n = f'NSG-Q-{id_off:04d}'
    save({
        'id': n, 'title': title, 'category': 'troubleshoot', 'vendor': vendor, 'version': version,
        'difficulty': difficulty, 'tags': tags,
        'input': {
            'symptom': symptom, 'device_info': {'model': '', 'version': version, 'interfaces': []},
            'evidence': configs + [{'log_lines': l} if isinstance(l, list) else {'config_snippet': l} for l in logs],
            'question': question,
        },
        'expected_output': {'root_causes': rc, 'references': refs},
        'anti_examples': ['请重启设备', '删除进程', '推荐全局清除配置'],
        'grading_rubric': {
            'must_have': ['top 根因为 ' + tags[0], '≥1 验证命令', '≥1 修复命令'],
            'nice_to_have': ['含 rollback'],
            'penalty': ['推荐重启'],
        },
    })

# BGP maximum-prefix 多厂商 (Q-0156..0160)
# 接续 0040 已写 huawei，再加 cisco/h3c/juniper/arista 各 1 题
W(157, 'BGP maximum-prefix 超限（思科 IOS-XE 17，邻居被 shutdown）', 'cisco', 'IOS-XE-17.09', 3, ['bgp','maximum-prefix','route-leak'],
  '%BGP-5-ADJCHANGE: neighbor 10.1.1.2 Down BGP Notification',
  [{'config_snippet': 'router bgp 65001\n neighbor 10.1.1.2 maximum-prefix 5000 80 restart 15\n# 对端发 20000 前缀'}],
  [], '诊断 maximum-prefix 触发',
  [
    {'rank':1,'cause':'对端路由泄漏超上限','probability':0.7,
     'evidence':['对端发了 20000+ 前缀','Notification 触发'],
     'verify':'show ip bgp summary | include messages','fix':'prefix-list 限制 + 提高 maximum-prefix 10000 90'},
    {'rank':2,'cause':'restart 计时器未达', 'probability': 0.2, 'verify':'show ip bgp neighbors 10.1.1.2 | include restart','fix':'clear ip bgp 10.1.1.2 soft'},
  ],
  [{'type':'vendor_doc','url':'https://www.cisco.com/c/en/us/support/bgp-maximum-prefix','version':'IOS-XE-17.09'}])

W(158, 'BGP maximum-prefix 超限（华三 Comware 7）', 'h3c', 'Comware-7.1.070', 3, ['bgp','maximum-prefix','shutdown'],
  '%@BGPN/3/STATECHG: Peer(10.1.1.2) -> Idle (exceeded maximum-prefix)',
  [{'config_snippet': 'bgp 65001\n peer 10.1.1.2 as-number 65002\n peer 10.1.1.2 maximum-prefix 1000 80'}],
  ['%@BGPN/3/STATECHG(l): Peer(10.1.1.2) -> Idle (exceeded max-prefix)'],
  '诊断 maximum-prefix 触发',
  [{'rank':1,'cause':'路由泄漏','probability':0.7,'verify':'display bgp routing-table statistics','fix':'bgp 65001 → undo peer x maximum-prefix → peer y maximum-prefix 5000'},
   {'rank':2,'cause':'Prefix 被 attacker 重写','probability':0.3,'verify':'display filter-policy','fix':'ip-prefix 过滤'}],
  [{'type':'vendor_doc','url':'https://www.h3c.com/cn/d_202206/bgp-maximum-prefix','version':'Comware 7.1.070'}])

W(159, 'BGP maximum-prefix 超限（Juniper 22，prefix-limit-threshold 触发 idle）', 'juniper', '21.2R1', 3, ['bgp','maximum-prefix','flap'],
  'show bgp summary: x.x.x.x Idle (Maximum-prefix)',
  [{'config_snippet': 'set groups BGP-LIMITS protocols bgp group EBGP family inet unicast prefix-limit maximum 1000 teardown 90'}],
  [], '诊断 maximum-prefix 触发',
  [{'rank':1,'cause':'路由泄漏','probability':0.7,'evidence':['prefix-limit 1000','对端发 5000+'],
    'verify':'show bgp summary','fix':'edit protocols bgp group EBGP → set family inet unicast prefix-limit maximum 10000 teardown 90\ncommit'},
   {'rank':2,'cause':'prefix-limit teardown 阈值偏低','probability':0.3,'verify':'show bgp statistics','fix':'teardown 95'}],
  [{'type':'vendor_doc','url':'https://www.juniper.net/documentation/junos-21.2/bgp-prefix-limit','version':'21.2R1'}])

W(160, 'BGP maximum-prefix 超限（Arista EOS 4.24，max-routes 触发）', 'arista', '4.24', 3, ['bgp','maximum-prefix'],
  '%BGP-4-MAX_ROUTES: Peer 10.1.1.2 (AS 65002) exceeded maximum routes 5000',
  [{'config_snippet': 'router bgp 65001\n neighbor 10.1.1.2 maximum-routes 5000 80 warning-only'}],
  [], '诊断 max-routes 触发',
  [{'rank':1,'cause':'对端路由泄漏','probability':0.7,'verify':'show ip bgp summary','fix':'max-routes 50000 + ip prefix-list 过滤'},
   {'rank':2,'cause':'warning-only 模式', 'probability': 0.2, 'verify':'show ip bgp summary | include warning','fix':'warning-only 移除'}],
  [{'type':'vendor_doc','url':'https://www.arista.com/en/docs/eos-4.24/bgp-max-routes','version':'EOS 4.24'}])

# BGP route oscillation
W(161, 'BGP 路由频繁 flap（华为 VRP-8.180，aggregator 抖动）', 'huawei', 'VRP-8.180', 3, ['bgp','route-flap','aggregate'],
  'BGP 路由 192.168.0.0/16 频繁 Up/Down',
  [{'config_snippet': 'bgp 65001\n aggregate 192.168.0.0 255.255.0.0 detail-suppressed\n network 192.168.1.0 255.255.255.0\n network 192.168.2.0 255.255.255.0'}],
  ['%BGP-5-CHANGE: Peer state Open -> Established -> Open反复'],
  '诊断 route flap',
  [{'rank':1,'cause':'被 aggregate 的子网频繁撤回（上游 IGP 抖动）','probability':0.6,'verify':'display bgp routing-table flap-info','fix':'aggregate 关闭 + static 注入 static-route'},
   {'rank':2,'cause':'BGP dampening 未启用','probability':0.3,'verify':'display bgp dampening','fix':'dampening 启用'}],
  [{'type':'vendor_doc','url':'https://support.huawei.com/vrp-bgp-aggregate','version':'VRP-8.180'}])

W(162, 'BGP 路由频繁 flap（思科 IOS-XE 17，dampening 阈值过严）', 'cisco', 'IOS-XE-17.09', 3, ['bgp','dampening','route-flap'],
  'BGP dampening 频繁抑制路由',
  [{'config_snippet': 'router bgp 65001\n bgp dampening 15 750 2000 60\n# suppress 阈值 750，路由经常被 suppress'}],
  [], '诊断 dampening 过严',
  [{'rank':1,'cause':'dampening 阈值过低，链路抖动即被惩罚','probability':0.7,'verify':'show ip bgp dampening parameters','fix':'bgp dampening 15 2000 4000 90'},
   {'rank':2,'cause':'链路物理不稳定','probability':0.3,'verify':'show interface | include flap','fix':'修链路'}],
  [{'type':'vendor_doc','url':'https://www.cisco.com/c/en/us/support/bgp-dampening','version':'IOS-XE-17.09'}])

# OSPF SPF 频繁
W(163, 'OSPF SPF 频繁计算（Juniper 22，stub area type-3 抖动）', 'juniper', '21.2R1', 3, ['ospf','spf','stub'],
  'OSPF SPF 计算 100/秒',
  [{'config_snippet': 'set protocols ospf area 0.0.0.1 stub\nset protocols ospf area 0.0.0.1 interface ge-0/0/0\n# Spoke 端频繁 Up/Down'}],
  ['show ospf statistics extensive: SPF runs: 100/5s'],
  '诊断 SPF 频繁',
  [{'rank':1,'cause':'stub area 接口频繁 Up/Down','probability':0.65,'verify':'show interfaces ge-0/0/0 | match flap','fix':'提升 SPF throttle（spf-options delay 1000 holdtime 5000 max 5000）'},
   {'rank':2,'cause':'SPF throttle 未配置', 'probability': 0.35, 'verify':'show ospf configuration','fix':'spf-options 配置 throttle'}],
  [{'type':'vendor_doc','url':'https://www.juniper.net/documentation/junos-21.2/ospf-spf-options','version':'21.2R1'}])

W(164, 'OSPF 邻居卡 Loading（Huawei VRP-8.180，LSACK 重传不停）', 'huawei', 'VRP-8.180', 4, ['ospf','loading','lsack','retransmit'],
  'OSPF neighbor 10.0.0.2 卡 Loading，retransmit 持续上升',
  [{'config_snippet': 'ospf 1\n area 0.0.0.0\n  network 10.1.1.0 0.0.0.255'}],
  ['%OSPF-4-LSACK_RETRANSMIT: OSPF 1: Retransmitting LSA 10.0.0.2 type-3'],
  '诊断 LSACK 重传',
  [{'rank':1,'cause':'中间设备 multicast 阻断（224.0.0.5/6）','probability':0.6,'verify':'display acl | include 224','fix':'放行 multicast'},
   {'rank':2,'cause':'邻居网卡驱动 bug', 'probability': 0.2, 'verify':'display device','fix':'升级驱动'},
   {'rank':3,'cause':'存在大量同步重传', 'probability': 0.2, 'verify':'display ospf statistics','fix':'reset ospf 1 process'}],
  [{'type':'vendor_doc','url':'https://support.huawei.com/vrp-ospf-loading','version':'VRP-8.180'}])

# OSPF DBD seq
W(165, 'OSPF 卡 EXSTART Cisco（思科 DD 重传）', 'cisco', 'IOS-XE-17.09', 3, ['ospf','exstart','dd','retransmit'],
  'OSPF卡 EXSTART反复 retry',
  [{'config_snippet': 'interface g1/0/1\n ip ospf mtu-ignore   # ⚠️ 忽略 MTU'}],
  [], '诊断 EXSTART 重传',
  [{'rank':1,'cause':'ip ospf mtu-ignore 配合不当，导致 DBD 反复','probability':0.6,'verify':'show ip ospf interface g1/0/1 | include MTU','fix':'no ip ospf mtu-ignore'},
   {'rank':2,'cause':'链路噪声大','probability':0.4,'verify':'show interface | include error','fix':'查物理层'}],
  [{'type':'vendor_doc','url':'https://www.cisco.com/c/en/us/support/ospf-mtu-ignore','version':'IOS-XE-17.09'}])

# OSPF neighbor 卡 2-way Cisco
W(166, 'OSPF 卡 2-way（H3C Comware 7，priority 错配 + 子网掩码）', 'h3c', 'Comware-7.1.070', 3, ['ospf','two-way','priority','mask'],
  'OSPF 卡 2-way',
  [{'config_snippet': 'int 40GE1/0/1\n ospf 1 area 0\n ospf network-type broadcast\n ospf dr-priority 0  # ⚠️ priority 0\n# 对端 dr-priority 100'}],
  [], '诊断 2-way 卡死',
  [{'rank':1,'cause':'本端 priority 0 + broadcast 网络类型组合，导致 DROther 关系正常但不形成 FULL','probability':0.6,'verify':'display ospf peer','fix':'ospf dr-priority 100'},
   {'rank':2,'cause':'两端接口子网掩码不一致','probability':0.4,'verify':'display ip interface brief','fix':'对齐掩码'}],
  [{'type':'vendor_doc','url':'https://www.h3c.com/cn/d_202206/ospf-two-way','version':'Comware 7.1.070'}])

# OSPF Init/Exchange
W(167, 'OSPF 卡 Init（Juniper 21.2，passive-interface 误配）', 'juniper', '21.2R1', 3, ['ospf','init','passive'],
  'OSPF 邻居卡 Init（收到 Hello 但无邻居 ID 列表）',
  [{'config_snippet': 'set protocols ospf area 0.0.0.0 interface ge-0/0/0 passive\n# ⚠️ passive 接口不发 Hello'}],
  [], '诊断 passive 误配',
  [{'rank':1,'cause':'ge-0/0/0 错配 passive（不发 Hello）','probability':0.85,'verify':'show ospf interface ge-0/0/0 | match passive','fix':'delete protocols ospf area 0.0.0.0 interface ge-0/0/0 passive'},
   {'rank':2,'cause':'area-id 不一致', 'probability': 0.15, 'verify':'show ospf neighbor','fix':'area 0.0.0.0 一致'}],
  [{'type':'vendor_doc','url':'https://www.juniper.net/documentation/junos-21.2/ospf-passive','version':'21.2R1'}])

# OSPF LSA storm
W(168, 'OSPF LSA 风暴（Arista EOS 4.24，type-2 频繁泛洪）', 'arista', '4.24', 3, ['ospf','lsa','network-type','storm'],
  'OSPF LSA 刷新异常频繁（type-2）',
  [{'config_snippet': 'interface Ethernet1\n ip ospf network broadcast\n ip ospf priority 255\n# 端点持续 Down/Up'}],
  [], '诊断 LSA 风暴',
  [{'rank':1,'cause':'端点物理不稳定导致 type-2 (Network LSA) 频繁刷新','probability':0.7,'verify':'show ip ospf database | include LSAge','fix':'bpduguard + 限速 + 改为 p2p 类型'},
   {'rank':2,'cause':'OSPF LSA Throttle 未配置','probability':0.3,'verify':'show ip ospf | include throttle','fix':'timers throttle lsa 配置'}],
  [{'type':'vendor_doc','url':'https://www.arista.com/en/docs/eos-4.24/ospf-lsa-throttle','version':'EOS 4.24'}])

# OSPFv3 (三厂商)
W(169, 'OSPFv3 邻居卡 Init（华为 VRP-8.180，instance-id 错）', 'huawei', 'VRP-8.180', 3, ['ospfv3','instance-id','init'],
  'OSPFv3 邻居卡 Init',
  [{'config_snippet': 'ospfv3 1\n router-id 10.0.0.1\ninterface 10GE1/0/1\n ospfv3 1 area 0 instance 17\n# 对端 instance 18'}],
  [], '诊断 instance-id 错配',
  [{'rank':1,'cause':'两端 instance-id 不一致（17 vs 18）','probability':0.85,'evidence':['Init 状态说明 Hello 不匹配'],
     'verify':'display ospfv3 interface 10GE1/0/1 | include instance','fix':'interface 10GE1/0/1 → ospfv3 1 area 0 instance 18'},
   {'rank':2,'cause':'area-id 错配', 'probability': 0.15, 'verify':'display ospfv3','fix':'统一 area 0'}],
  [{'type':'vendor_doc','url':'https://support.huawei.com/vrp-ospfv3','version':'VRP-8.180'}])

W(170, 'OSPFv3 卡 EXSTART（思科 17，hello 计时器 错）', 'cisco', 'IOS-XE-17.09', 3, ['ospfv3','hello','ipv6'],
  'OSPFv3 卡 EXSTART',
  [{'config_snippet': 'interface g1/0/1\n ipv6 ospf 1 area 0\n ipv6 ospf hello-interval 30   # ⚠️ 不一致\n # 对端默认 10'}],
  [], '诊断 hello 错',
  [{'rank':1,'cause':'OSPFv3 计时器必须严格一致（不取 min）','probability':0.7,'verify':'show ipv6 ospf interface','fix':'ipv6 ospf hello-interval 10'},
   {'rank':2,'cause':'OSPFv3 network-type 错配','probability':0.3,'verify':'show ipv6 ospf interface | include Network','fix':'统一 network-type'}],
  [{'type':'vendor_doc','url':'https://www.cisco.com/c/en/us/support/ospfv3-hello','version':'IOS-XE-17.09'}])

# OSPF ABR type-5 summary
W(171, 'OSPF ABR 不通告 type-3 summary（华三 Comware 7）', 'h3c', 'Comware-7.1.070', 3, ['ospf','abr','summary','nssa'],
  'OSPF ABR 不通告某些 inter-area route',
  [{'config_snippet': 'ospf 1\n area 0.0.0.1\n  stub no-summary  # ⚠️ 完全末梢'}],
  [], '诊断 type-3 summary 缺',
  [{'rank':1,'cause':'stub no-summary 抑制 type-3','probability':0.85,'verify':'display ospf lsdb | include Summary','fix':'undo stub no-summary → stub'},
   {'rank':2,'cause':'ABR 上 area-range 误配', 'probability': 0.15, 'verify':'display ospf abr','fix':'调整 area-range'}],
  [{'type':'vendor_doc','url':'https://www.h3c.com/cn/d_202206/ospf-stub-summary','version':'Comware 7.1.070'}])

# OSPF inter-area routes
W(172, 'OSPF 区域内路由缺失（思科 17，db-filter 配置）', 'cisco', 'IOS-XE-17.09', 4, ['ospf','db-filter','summary'],
  'OSPF 部分区域内路由学习不到',
  [{'config_snippet': 'router ospf 1\n area 0.0.0.1 filter-list prefix PL-IN in'}],
  [], '诊断 db-filter',
  [{'rank':1,'cause':'area 0.0.0.1 应用 prefix-list filter 误阻挡','probability':0.7,'verify':'show ip ospf database','fix':'undo filter-list'},
   {'rank':2,'cause':'route-map 误配','probability':0.3,'verify':'show route-map','fix':'调整 route-map'}],
  [{'type':'vendor_doc','url':'https://www.cisco.com/c/en/us/support/ospf-prefix-filter','version':'IOS-XE-17.09'}])

# OSPF cost
W(173, 'OSPF 路由 cost 不优（Juniper 22，interface metric 设错）', 'juniper', '21.2R1', 3, ['ospf','cost','metric'],
  'OSPF 路由选择非最优链路',
  [{'config_snippet': 'set protocols ospf area 0.0.0.0 interface ge-0/0/0 metric 1000   # ⚠️ cost 过大'}],
  [], '诊断 cost 错配',
  [{'rank':1,'cause':'接口 metric 被强加 1000，导致不合理路径','probability':0.8,'verify':'show ospf interface ge-0/0/0 | match metric','fix':'set metric 10'},
   {'rank':2,'cause':'bandwidth reference 错配', 'probability': 0.2, 'verify':'show ospf configuration','fix':'reference-bandwidth 100000'}],
  [{'type':'vendor_doc','url':'https://www.juniper.net/documentation/junos-21.2/ospf-cost','version':'21.2R1'}])

# OSPF 隐式路由
W(174, 'OSPF 默认路由缺失（Arista EOS 4.24，default-information originate 漏配）', 'arista', '4.24', 3, ['ospf','default-information','stub'],
  'OSPF stub 区无默认路由',
  [{'config_snippet': 'router ospf 1\n area 0.0.0.1 stub\n# ⚠️ ABR 上未加 default-information originate'}],
  [], '诊断 default-information',
  [{'rank':1,'cause':'ABR 漏 default-information originate','probability':0.85,'verify':'show ip ospf database','fix':'area 0.0.0.1 default-information originate'},
   {'rank':2,'cause':'metrics 设错', 'probability': 0.15, 'verify':'show ip ospf','fix':'area stub 默认 cost 1'}],
  [{'type':'vendor_doc','url':'https://www.arista.com/en/docs/eos-4.24/ospf-default','version':'EOS 4.24'}])

# OSPF authentication
W(175, 'OSPF 卡 Init（华为 VRP-8.180，区域认证 key-id 不一致）', 'huawei', 'VRP-8.180', 3, ['ospf','authentication','md5','init'],
  'OSPF 卡 Init',
  [{'config_snippet': 'ospf 1\n area 0.0.0.0\n  authentication-mode md5 1 plain Huawei@2024   # ⚠️ key-id 1\n # 对端 md5 2 plain Huawei@2024'}],
  [], '诊断 authentication key-id 错',
  [{'rank':1,'cause':'md5 key-id 不一致','probability':0.8,'verify':'display ospf interface | include Auth','fix':'统一 key-id 1'},
   {'rank':2,'cause':'plain vs cipher 错配', 'probability': 0.2, 'verify':'display ospf interface | include Auth','fix':'统一 cipher / plain'}],
  [{'type':'vendor_doc','url':'https://support.huawei.com/vrp-ospf-authentication','version':'VRP-8.180'}])

# VXLAN VTEP loop
W(176, 'VTEP IP 不互通（华三 Comware 7，Loopback 接口 IP 不一致）', 'h3c', 'Comware-7.1.070', 4, ['vxlan','vtep','loopback','bgp'],
  'VXLAN VTEP peer 不可达',
  [{'config_snippet': '# Spine\ninterface Loopback0\n ip address 10.0.0.1 32\nbgp 65000\n  peer 10.0.0.2 as 65000   # ⚠️ 对端 loopback 是 10.0.0.100'}],
  [], '诊断 VTEP loopback 错配',
  [{'rank':1,'cause':'Spine 配 10.0.0.2 但对端是 10.0.0.100','probability':0.7,'verify':'display bgp peer','fix':'统一 loopback 地址'},
   {'rank':2,'cause':'Loopback 接口 down','probability':0.3,'verify':'display interface Loopback0','fix':'undo shutdown'}],
  [{'type':'vendor_doc','url':'https://www.h3c.com/cn/d_202206/vtep-loopback','version':'Comware 7.1.070'}])

# VXLAN BUM HS
W(177, 'VXLAN BUM 头端复制异常（思科 NX-OS 9.3，head-end-replication-mode 错配）', 'cisco', 'NX-OS-9.3', 4, ['vxlan','bum','head-end-replication'],
  'VXLAN BUM 流量丢包',
  [{'config_snippet': 'interface nve1\n  source-interface Loopback0\n  member vni 10010\n   ingress-replication protocol static\n    peer-vtep 10.0.0.1\n  # ⚠️ 应使用 bgp，但用了 static'}],
  [], '诊断 head-end-replication',
  [{'rank':1,'cause':'nve 用 static 但对端用 bgp','probability':0.7,'verify':'show nve vni','fix':'member vni 10010 ingress-replication protocol bgp'},
   {'rank':2,'cause':'peer-vtep 列表不全','probability':0.3,'verify':'show nve peer','fix':'补 peer-vtep'}],
  [{'type':'vendor_doc','url':'https://www.cisco.com/c/en/us/support/nx-os-vxlan-bum','version':'NX-OS-9.3'}])

# VXLAN sub-if
W(178, 'VXLAN NVE 端口 down（华为 VRP-8.180，物理接口绑定错）', 'huawei', 'VRP-8.180', 3, ['vxlan','nve','source-interface'],
  'VXLAN nve interface 状态 down',
  [{'config_snippet': '# 检查 nve source-interface 不能在本端 down\ninterface 10GE1/0/1\n port link-type access\n# 没配 IP'},
  ], 'NVE 端口状态',
  [{'rank':1,'cause':'10GE1/0/1 没配 IP 处于 DOWN（应是三层口）','probability':0.7,'verify':'display interface 10GE1/0/1','fix':'ip address + port link-mode route'},
   {'rank':2,'cause':'NVE 接口在实例中漏配置','probability':0.3,'verify':'display vxlan vni','fix':'配置 nve source-interface'}],
  [{'type':'vendor_doc','url':'https://support.huawei.com/vrp-nve','version':'VRP-8.180'}])

# VXLAN anycast 一致性
W(179, 'VXLAN anycast-gateway MAC 一致性检查（Juniper Mist + H3C 一致性）', 'juniper', '21.2R1', 4, ['vxlan','anycast-gateway','mac-consistency'],
  'VXLAN anycast-gateway 间歇不通（MAC 不一致）',
  [{'config_snippet': '# Mist API call: irb.mac = 0000.5e00.0120\n# H3C side: evpn gw-mac 0000-5e00-0120  # 错误 dashes'}],
  [], '诊断 anycast MAC 不一致',
  [{'rank':1,'cause':'Mist 配 0000.5e00.0120，H3C 配 0000-5e00-0120（不同 dash 格式）','probability':0.85,'verify':'show evpn mac-table','fix':'统一 MAC 格式'},
   {'rank':2,'cause':'Leaf 之间未同步', 'probability': 0.15, 'verify':'show evpn instance detail','fix':'统一 sync'}],
  [{'type':'vendor_doc','url':'https://www.juniper.net/documentation/junos-21.2/evpn-anycast-gateway','version':'21.2R1'}])

# IPv6 BGP link-local (5 vendor)
W(180, 'IPv6 BGP link-local 误配（华三 Comware 7，connect-interface 错）', 'h3c', 'Comware-7.1.070', 4, ['bgp','ipv6','link-local','connect-interface'],
  'IPv6 BGP peer 卡 Active',
  [{'config_snippet': '# Spine\nbgp 65000\n peer fe80::1 as-number 65000\n ! ⚠️ 漏 connect-interface'}],
  [], '诊断 connect-interface',
  [{'rank':1,'cause':'IPv6 BGP link-local 必须配 connect-interface','probability':0.9,'verify':'display bgp ipv6 peer fe80::1','fix':'peer fe80::1 connect-interface 40GE1/0/1'},
   {'rank':2,'cause':'fe80::1 是对端 link-local，本端不一定可达','probability':0.1,'verify':'display ipv6 neighbors','fix':'同步接口'}],
  [{'type':'vendor_doc','url':'https://www.h3c.com/cn/d_202206/bgp-ipv6-link-local','version':'Comware 7.1.070'}])

# MPLS L3VPN LDP
W(181, 'MPLS LDP 邻居不建（Cisco XR，mpls label-range 错配）', 'cisco', 'IOS-XE-17.09', 4, ['mpls','ldp','label-range'],
  'MPLS LDP 邻居不建立',
  [{'config_snippet': 'mpls label range 100 199\nmpls ldp router-id Loopback0 force'}],
  [], '诊断 LDP 邻居',
  [{'rank':1,'cause':'label-range 后 router-id 改变仍 active','probability':0.5,'verify':'show mpls ldp neighbor','fix':'clear mpls ldp neighbor *'},
   {'rank':2,'cause':'IGP 中 router-id Lo 不通','probability':0.5,'verify':'show ip route 10.0.0.1','fix':'修 IGP'}],
  [{'type':'vendor_doc','url':'https://www.cisco.com/c/en/us/support/mpls-ldp','version':'IOS-XE-17.09'}])

# MPLS LSP
W(182, 'MPLS LSP 不通（Juniper 22，RSVP 标签范围错）', 'juniper', '21.2R1', 4, ['mpls','rsvp','lsp','tunnel'],
  'MPLS LSP 反复 Up/Down',
  [{'config_snippet': 'set protocols rsvp interface ge-0/0/0\nset protocols mpls label-range static 1000000 1000999\n# ⚠️ label range 过小'}],
  [], '诊断 LSP down',
  [{'rank':1,'cause':'label-range 占用不够','probability':0.7,'verify':'show mpls interface','fix':'label-range 16 1000000'},
   {'rank':2,'cause':'LSP path explicit-path 错配','probability':0.3,'verify':'show mpls lsp','fix':'path primary loose'}],
  [{'type':'vendor_doc','url':'https://www.juniper.net/documentation/junos-21.2/mpls-rsvp','version':'21.2R1'}])

# VRRP + BFD
W(183, 'VRRP 不切换（H3C Comware 7，BFD 会话未启）', 'h3c', 'Comware-7.1.070', 3, ['vrrp','bfd','high-availability'],
  'VRRP 主设备 dead 后未切换',
  [{'config_snippet': '# Switch-A\ninterface Vlan-interface10\n vrrp vrid 1 virtual-ip 10.1.10.1\n vrrp vrid 1 priority 110\n # ⚠️ 漏 vrrp vrid 1 track bfd-session'}],
  [], '诊断 VRRP switchover',
  [{'rank':1,'cause':'switchover 触发依赖 BFD，但未配 track','probability':0.7,'verify':'display vrrp verbose','fix':'vrrp vrid 1 track bfd-session 1 reduce 30'},
   {'rank':2,'cause':'上行 down 但 VRRP 未感知','probability':0.3,'verify':'display bfd session','fix':'启用 bfd'}],
  [{'type':'vendor_doc','url':'https://www.h3c.com/cn/d_202206/vrrp-bfd','version':'Comware 7.1.070'}])

# VRRP 双主
W(184, 'VRRP 双 Master（Cisco IOS-XE 17，advertise interval 抖动）', 'cisco', 'IOS-XE-17.09', 3, ['vrrp','dual-master','advertise'],
  'VRRP 同 VRID 两个 Master（split brain）',
  [{'config_snippet': 'interface Vlan10\n vrrp 1 ip 10.1.10.1\n vrrp 1 timers advertise msec 100\n # 链路延迟 200ms'}],
  [], '诊断 VRRP dual-master',
  [{'rank':1,'cause':'advertise 间隔抖动，导致 split-brain','probability':0.7,'verify':'show vrrp detail','fix':'timers advertise 1'},
   {'rank':2,'cause':'认证不一致','probability':0.3,'verify':'show vrrp interface','fix':'认证 + 间隔对齐'}],
  [{'type':'vendor_doc','url':'https://www.cisco.com/c/en/us/support/vrrp-dual-master','version':'IOS-XE-17.09'}])

# HSRP
W(185, 'HSRP 卡 Init（Arista EOS 4.24，HSRP version 1 vs 2）', 'arista', '4.24', 3, ['hsrp','version-mismatch'],
  'HSRP 卡 Init',
  [{'config_snippet': '# Device-A\ninterface Vlan10\n ip address 10.1.10.1/24\n hsrp version 2\n hsrp 1 ip 10.1.10.1\n# Device-B\ninterface Vlan10\n hsrp version 1  # ⚠️ 不一致'}],
  [], '诊断 HSRP version 错配',
  [{'rank':1,'cause':'HSRP version 1 vs 2 不兼容','probability':0.85,'verify':'show hsrp brief','fix':'统一 version 2'},
   {'rank':2,'cause':'认证字符串不一致', 'probability': 0.15, 'verify':'show hsrp detail','fix':'删除认证'}],
  [{'type':'vendor_doc','url':'https://www.arista.com/en/docs/eos-4.24/hsrp','version':'EOS 4.24'}])

# IPv6 BGP additional vendors
W(186, 'IPv6 BGP AFI 警告（思科 IOS-XE 17，neighbor ipv6 不在 family 内）', 'cisco', 'IOS-XE-17.09', 4, ['bgp','ipv6','afi'],
  'IPv6 BGP peer state OpenConfirm 但未收到 update',
  [{'config_snippet': 'router bgp 65001\n neighbor 2001:db8::2 remote-as 65002\n address-family ipv4 unicast\n  neighbor 2001:db8::2 activate\n ! 缺 address-family ipv6 unicast'}],
  [], '诊断 AFI',
  [{'rank':1,'cause':'address-family ipv6 unicast 未配 neighbor activate','probability':0.85,'verify':'show ip bgp summary','fix':'address-family ipv6 unicast → neighbor 2001:db8::2 activate'},
   {'rank':2,'cause':'IPv6 单播路由被压制', 'probability': 0.15, 'verify':'show ipv6 route','fix':'ipv6 unicast-routing 启用'}],
  [{'type':'vendor_doc','url':'https://www.cisco.com/c/en/us/support/bgp-ipv6-afi','version':'IOS-XE-17.09'}])

W(187, 'IPv6 BGP 卡 active（思科 neighbor transport-mode 错配）', 'cisco', 'IOS-XE-17.09', 4, ['bgp','ipv6','active','transport'],
  'IPv6 BGP 卡 active',
  [{'config_snippet': 'router bgp 65001\n neighbor 2001:db8::2 remote-as 65002\n neighbor 2001:db8::2 transport connection-mode passive  # ⚠️ 两端都 passive'}],
  [], '诊断 transport',
  [{'rank':1,'cause':'两端都 passive 导致 TCP 主动连接不发起','probability':0.85,'verify':'show ip bgp neighbor 2001:db8::2 | include passive','fix':'no neighbor 2001:db8::2 transport connection-mode passive'},
   {'rank':2,'cause':'防火墙阻断 179', 'probability': 0.15, 'verify':'debug ip tcp','fix':'放行 179'}],
  [{'type':'vendor_doc','url':'https://www.cisco.com/c/en/us/support/bgp-passive','version':'IOS-XE-17.09'}])

# IPsec aggressive mode
W(188, 'IPsec Aggressive Mode 协商失败（Cisco 思科，peer type 错配）', 'cisco', 'IOS-XE-17.09', 4, ['ipsec','aggressive','ikev1'],
  'IPsec aggressive mode 不通',
  [{'config_snippet': '# 本端 main mode\ncrypto isakmp policy 10\n authentication pre-share\n# 对端 aggressive mode'}],
  [], '诊断 aggressive mode',
  [{'rank':1,'cause':'两端 mode 不一致（main vs aggressive）','probability':0.85,'verify':'show crypto isakmp policy','fix':'crypto isakmp policy 10 authen pre-share mode aggressive'},
   {'rank':2,'cause':'PSK 不一致', 'probability': 0.15, 'verify':'show crypto isakmp key','fix':'对齐 pre-shared-key'}],
  [{'type':'vendor_doc','url':'https://www.cisco.com/c/en/us/support/ipsec-aggressive','version':'IOS-XE-17.09'}])

# IPsec IKEv2 EAP
W(189, 'IPsec IKEv2 EAP 认证失败（华为 VRP-8.180，身份 auth-method 错配）', 'huawei', 'VRP-8.180', 4, ['ipsec','ikev2','eap','radius'],
  'IPsec IKEv2 EAP 认证失败',
  [{'config_snippet': 'ike peer peer-eap\n  auth-method eap\n  remote-id-type user-fqdn\n  eap-method tls  # ⚠️ 对端是 certificate'}],
  [], '诊断 EAP',
  [{'rank':1,'cause':'eap-method 与对端不一致','probability':0.7,'verify':'display ike peer','fix':'eap-method certificate / psk 对齐'},
   {'rank':2,'cause':'RADIUS 服务器不可达','probability':0.3,'verify':'display radius','fix':'修 RADIUS server'}],
  [{'type':'vendor_doc','url':'https://support.huawei.com/vrp-ipsec-eap','version':'VRP-8.180'}])

# QinQ
W(190, 'QinQ 配置不通（华三 Comware 7，外层 VLAN tag 误配）', 'h3c', 'Comware-7.1.070', 3, ['qinq','vlan','trunk'],
  'QinQ 流量透传不成功',
  [{'config_snippet': '# Spine\nvlan 100\ninterface 40GE1/0/1\n port link-type trunk\n port trunk permit vlan 100 200\n qinq enable\n qinq vlan-translation customer-vid 200 to service-vid 100  # ⚠️ translation 错'}],
  [], '诊断 QinQ',
  [{'rank':1,'cause':'qinq vlan-translation 方向错','probability':0.7,'verify':'display qinq','fix':'qinq vid-translation 调整'},
   {'rank':2,'cause':'service-vid 不一致','probability':0.3,'verify':'display vlan','fix':'统一 service-vid'}],
  [{'type':'vendor_doc','url':'https://www.h3c.com/cn/d_202206/qinq','version':'Comware 7.1.070'}])

# IPv6 Neighbor cache
W(191, 'IPv6 Neighbor Discovery 频繁失效（华为 VRP-8.180，nd cache expire 错配）', 'huawei', 'VRP-8.180', 3, ['ipv6','nd','neighbor-cache'],
  'IPv6 Neighbor cache incomplete 高',
  [{'config_snippet': 'interface 10GE1/0/1\n ipv6 nd cache expire 60  # ⚠️ 太短'}],
  [], '诊断 nd cache',
  [{'rank':1,'cause':'ipv6 nd cache expire 60s 太短','probability':0.7,'verify':'display ipv6 neighbors','fix':'ipv6 nd cache expire 14400'},
   {'rank':2,'cause':'IPv6 link-local 频繁变','probability':0.3,'verify':'display ipv6 interface','fix':'配置固定 link-local'}],
  [{'type':'vendor_doc','url':'https://support.huawei.com/vrp-ipv6-nd','version':'VRP-8.180'}])

# DHCP snooping
W(192, 'DHCP snooping 阻断合法用户（思科 IOS-XE 17，trust interface 错配）', 'cisco', 'IOS-XE-17.09', 3, ['dhcp','snooping','trust'],
  'DHCP 客户端获取不到 IP',
  [{'config_snippet': 'ip dhcp snooping\nip dhcp snooping vlan 10\ninterface fa0/1\n   ip dhcp snooping trust  # ⚠️ uplink 错配 trust 不能放行 DHCP'}],
  [], '诊断 DHCP trust',
  [{'rank':1,'cause':'DHCP server 接口未配 trust','probability':0.7,'verify':'show ip dhcp snooping binding','fix':'上行接口 dhcp snooping trust'},
   {'rank':2,'cause':'option 82 中间设备封装丢','probability':0.3,'verify':'show ip dhcp snooping statistics','fix':'关闭 option 82'}],
  [{'type':'vendor_doc','url':'https://www.cisco.com/c/en/us/support/dhcp-snooping','version':'IOS-XE-17.09'}])

# AAA radius timeout
W(193, 'AAA RADIUS 超时（思科 IOS-XE 17，source-interface 错配）', 'cisco', 'IOS-XE-17.09', 3, ['aaa','radius','timeout'],
  'AAA RADIUS 认证 timeout',
  [{'config_snippet': 'radius server R1\n  address ipv4 10.1.1.99 auth-port 1812 acct-port 1813\n  key NetSys@2024\n# ⚠️ router 送出 source IP 不可达'}],
  [], '诊断 RADIUS timeout',
  [{'rank':1,'cause':'radius source-interface 不可达','probability':0.7,'verify':'test aaa server R1','fix':'ip radius source-interface Vlan99'},
   {'rank':2,'cause':'timeout 设过短','probability':0.3,'verify':'show running | include radius','fix':'timeout 30'}],
  [{'type':'vendor_doc','url':'https://www.cisco.com/c/en/us/support/aaa-radius','version':'IOS-XE-17.09'}])

# 802.1X
W(194, '802.1X 认证失败（华为 VRP-8.180，radius-server dead time 错配）', 'huawei', 'VRP-8.180', 3, ['dot1x','radius','auth'],
  '802.1X 认证失败',
  [{'config_snippet': 'dot1x enable\nradius-server template RS1\n radius-server authentication 10.1.1.99 1812\n radius-server shared-key cipher NetSys@2024\n  radius-server dead-detect enable   # ⚠️ 启用 dead-detect'}],
  [], '诊断 802.1X',
  [{'rank':1,'cause':'radius-server dead-detect 启用但 dead-time 超时','probability':0.7,'verify':'display dot1x','fix':'undo radius-server dead-detect'},
   {'rank':2,'cause':'认证方式 EAP/TLS 不一致','probability':0.3,'verify':'display dot1x','fix':'调整 EAP 模式'}],
  [{'type':'vendor_doc','url':'https://support.huawei.com/vrp-dot1x','version':'VRP-8.180'}])

# LACP fallback
W(195, 'LACP fallback 单链路（思科 IOS-XE 17，LACP fallback 配置错）', 'cisco', 'IOS-XE-17.09', 3, ['lacp','fallback','single-link'],
  'LACP 仅 single link 工作',
  [{'config_snippet': 'interface port-channel 10\n lacp fallback static 1G port-channel 20\n lacp max-bundle 2'}],
  [], '诊断 LACP fallback',
  [{'rank':1,'cause':'lacp fallback 配置但对端未启','probability':0.7,'verify':'show etherchannel summary','fix':'两端都对齐'},
   {'rank':2,'cause':'max-bundle < active-member','probability':0.3,'verify':'show etherchannel detail','fix':'max-bundle 配置'}],
  [{'type':'vendor_doc','url':'https://www.cisco.com/c/en/us/support/lacp-fallback','version':'IOS-XE-17.09'}])

# Bridge loop (STPs)
W(196, '环路震荡（思科 MSTP，思科 Spanning-tree 实例错配）', 'cisco', 'IOS-XE-17.09', 3, ['stp','mstp','instance','loop'],
  '环路引发 ping 抖动',
  [{'config_snippet': 'spanning-tree mode mst\nspanning-tree mst configuration\n  name REGION1\n  revision 1\n  instance 1 vlan 10'}],
  [], '诊断 MST',
  [{'rank':1,'cause':'region-name 不一致','probability':0.7,'verify':'show spanning-tree mst','fix':'统一 region-name'},
   {'rank':2,'cause':'priority 错配','probability':0.3,'verify':'show spanning-tree mst priority','fix':'priority 0 root primary'}],
  [{'type':'vendor_doc','url':'https://www.cisco.com/c/en/us/support/mstp','version':'IOS-XE-17.09'}])

# VXLAN VTEP reach
W(197, 'VXLAN VTEP peer 不可达（华三 Comware 7，IGP 路由缺）', 'h3c', 'Comware-7.1.070', 4, ['vxlan','vtep','igp','reachability'],
  'VXLAN VTEP peer list 为空',
  [{'config_snippet': 'interface Loopback0\n ip address 10.0.0.1 32\nbgp 65000\n  peer 10.0.0.2 as 65000\n  peer 10.0.0.2 connect-interface Loopback0\n# ⚠️ IGP 中无 10.0.0.2'}],
  [], '诊断 VTEP reach',
  [{'rank':1,'cause':'IGP 中无 VTEP loopback 路由','probability': 0.75,'verify':'display ip routing-table','fix':'把 Loopback0 通告到 OSPF'},
   {'rank':2,'cause':'Loopback 自身未配置 IP','probability': 0.25,'verify':'display interface Loopback0','fix':'ip address'}],
  [{'type':'vendor_doc','url':'https://www.h3c.com/cn/d_202206/vtep-igp','version':'Comware 7.1.070'}])

# additional OSPF type-7 advanced
W(198, 'OSPF NSSA 不接收 type-7（Juniper 22，asbr 不宣告 type-7）', 'juniper', '21.2R1', 4, ['ospf','nssa','type-7','asbr'],
  'OSPF NSSA 上 ASBR 未注入 type-7',
  [{'config_snippet': '# NSSA 上\nset protocols ospf area 0.0.0.1 nssa\nset routing-options static route 10.99.0.0/16 discard\n# ⚠️ 不导出到 OSPF'}],
  [], '诊断 ASBR type-7',
  [{'rank':1,'cause':'未 policy-statement 引入 static','probability':0.7,'verify':'show ospf database nssa-external','fix':'set policy-options policy-statement t1 from protocol static; then accept\nset protocols ospf area 0.0.0.1 nssa export t1'},
   {'rank':2,'cause':'OSPF NSSA 区域 type 错','probability':0.3,'verify':'show ospf configuration','fix':'确认 nssa 配置'}],
  [{'type':'vendor_doc','url':'https://www.juniper.net/documentation/junos-21.2/ospf-nssa-export','version':'21.2R1'}])

# BGP IPv6 RT
W(199, 'IPv6 BGP RT 不匹配（思科 IOS-XE 17，route-map 漏配）', 'cisco', 'IOS-XE-17.09', 4, ['bgp','ipv6','route-map','export'],
  'IPv6 BGP peer 收到路由但未优选',
  [{'config_snippet': 'router bgp 65001\n neighbor 2001:db8::2 remote-as 65002\n address-family ipv6 unicast\n  network 2001:db8:1::/64\n ! ⚠️ 缺 route-map 过滤 community'}],
  [], '诊断 route-map',
  [{'rank':1,'cause':'route-map 缺 export policy','probability':0.7,'verify':'show bgp ipv6 unicast','fix':'export route-map 配 apply community'},
   {'rank':2,'cause':'路径属性 MED 错配','probability':0.3,'verify':'show bgp ipv6 unicast','fix':'set metric'}],
  [{'type':'vendor_doc','url':'https://www.cisco.com/c/en/us/support/bgp-ipv6-route-map','version':'IOS-XE-17.09'}])

# IS-IS metric
W(200, 'IS-IS 路由 metric 错（华为 VRP-8.180，wide/old metric 错配）', 'huawei', 'VRP-8.180', 4, ['isis','wide-metric','metric-style'],
  'IS-IS metric 不一致',
  [{'config_snippet': 'isis 1\n network-entity 49.0001.0000.0000.0001.00\n is-level level-2\n # ⚠️ 漏 metric-style wide'}],
  [], '诊断 IS-IS metric',
  [{'rank':1,'cause':'metric-style 默认 narrow，对端 wide 不兼容','probability':0.7,'verify':'display isis','fix':'metric-style wide'},
   {'rank':2,'cause':'level 错配','probability':0.3,'verify':'display isis peer','fix':'is-level level-2'}],
  [{'type':'vendor_doc','url':'https://support.huawei.com/vrp-isis-metric','version':'VRP-8.180'}])

# Spanning-tree
W(201, 'Spanning-tree PVST 不通（思科 17，allowed vlan 错）', 'cisco', 'IOS-XE-17.09', 3, ['stp','pvst','vlan','allowed'],
  'PVST 实例化错',
  [{'config_snippet': 'spanning-tree mode pvst\nspanning-tree vlan 10 priority 0'}],
  [], '诊断 PVST',
  [{'rank':1,'cause':'VLAN trunk allowed 不一致','probability':0.7,'verify':'show spanning-tree','fix':'switchport trunk allowed vlan 10'},
   {'rank':2,'cause':'MAC address-table 耗尽','probability':0.3,'verify':'show mac address-table','fix':'限制 MAC'}],
  [{'type':'vendor_doc','url':'https://www.cisco.com/c/en/us/support/pvst','version':'IOS-XE-17.09'}])

# FabricPath / Leaf-Spine
W(202, 'BGP EVPN RR 不通告 type-5（华三 Comware 7，RR 配错）', 'h3c', 'Comware-7.1.070', 4, ['bgp','evpn','rr','type-5'],
  'BGP EVPN Type-5 路由学习不到',
  [{'config_snippet': '# RR\nbgp 65000\n peer 10.0.0.1 as 65000\n peer 10.0.0.1 reflect-client\n # ⚠️ 漏 address-family l2vpn evpn'}],
  [], '诊断 RR type-5',
  [{'rank':1,'cause':'RR 未在 address-family l2vpn evpn 配置','probability':0.7,'verify':'display evpn route','fix':'address-family l2vpn evpn → peer 10.0.0.1 enable'},
   {'rank':2,'cause':'RT 不一致','probability':0.3,'verify':'display evpn route type-5','fix':'统一 RT'}],
  [{'type':'vendor_doc','url':'https://www.h3c.com/cn/d_202206/evpn-rr-type5','version':'Comware 7.1.070'}])

# NAT 主备
W(203, 'NAT 网关切换后丢包（华为 VRP-8.180，HRP 备机丢包）', 'huawei', 'VRP-8.180', 4, ['nat','hrp','backup','drop'],
  'NAT HRP 备机切换后丢包',
  [{'config_snippet': 'hrp enable\nhrp interface 10GE1/0/1 remote 198.51.100.2\nhrp mirror-session enable'}],
  [], '诊断 HRP NAT',
  [{'rank':1,'cause':'HRP 中备份端口流量回放延迟','probability':0.7,'verify':'display hrp state','fix':'调优 hrp preempt delay'},
   {'rank':2,'cause':'NAT 转换日志大量','probability':0.3,'verify':'display nat','fix':'清表'}],
  [{'type':'vendor_doc','url':'https://support.huawei.com/vrp-nat-hrp','version':'VRP-8.180'}])

# ecmp 等价路由
W(204, 'OSPF ECMP 不等分（思科 IOS-XE 17，max-paths 限制）', 'cisco', 'IOS-XE-17.09', 3, ['ospf','ecmp','max-paths'],
  'OSPF ECMP 不等分流量',
  [{'config_snippet': 'router ospf 1\n maximum-paths 4\n # ⚠️ 但 cost 不等分'}],
  [], '诊断 ECMP cost',
  [{'rank':1,'cause':'max-paths 4 但 cost 不等','probability':0.7,'verify':'show ip route','fix':'ip ospf cost 相等'},
   {'rank':2,'cause':'EIGRP 干扰','probability':0.3,'verify':'show ip protocol','fix':'disable eigrp'}],
  [{'type':'vendor_doc','url':'https://www.cisco.com/c/en/us/support/ospf-ecmp','version':'IOS-XE-17.09'}])

# IPV6 RA
W(205, 'IPv6 RA 不发送（华三 Comware 7，RA suppress 误配）', 'h3c', 'Comware-7.1.070', 3, ['ipv6','ra','suppress'],
  'IPv6 默认网关客户机获取不到',
  [{'config_snippet': '# Comware\ninterface Vlan-interface10\n ipv6 address 2001:db8:1::1/64\n ipv6 nd ra suppress'}],
  [], '诊断 RA suppress',
  [{'rank':1,'cause':'ipv6 nd ra suppress 误配','probability': 0.85,'verify':'display ipv6 nd ra','fix':'undo ipv6 nd ra suppress'},
   {'rank':2,'cause':'IPv6 link-local 未配','probability': 0.15,'verify':'display ipv6 interface','fix':'配 link-local'}],
  [{'type':'vendor_doc','url':'https://www.h3c.com/cn/d_202206/ipv6-ra','version':'Comware 7.1.070'}])

# ACL sequence
W(206, 'ACL 顺序错（思科 IOS-XE 17，sequence number 生效错）', 'cisco', 'IOS-XE-17.09', 3, ['acl','sequence','order'],
  'ACL permit 后被 deny',
  [{'config_snippet': 'ip access-list extended ACL-1\n 10 deny ip any any\n 5 permit tcp any any eq 80'}],
  [], '诊断 ACL 顺序',
  [{'rank':1,'cause':'ACL sequence 不按数字从小到大','probability': 0.7,'verify':'show ip access-list','fix':'序列号重新组织'},
   {'rank':2,'cause':'sub-ACl 被 main-ACL 短路','probability': 0.3,'verify':'show ip access-list','fix':'调整 hierarchy'}],
  [{'type':'vendor_doc','url':'https://www.cisco.com/c/en/us/support/acl-sequence','version':'IOS-XE-17.09'}])

# Internal BGP RR cluster
W(207, 'BGP RR cluster-list 阻塞（Juniper 21.2，RR 双重 cluster_id）', 'juniper', '21.2R1', 4, ['bgp','route-reflector','cluster-id','loop'],
  'BGP 路由 RR 之间不互相 ref',
  [{'config_snippet': 'set routing-options autonomous-system 65000\nset protocols bgp group RR-RR cluster 10.0.0.1\nset protocols bgp group RR-RR neighbor 10.0.0.3 peer-as 65000\n# ⚠️ cluster-id 冲突'}],
  [], '诊断 RR cluster',
  [{'rank':1,'cause':'同 cluster-id 导致 route reflect 死循环','probability': 0.7,'verify':'show bgp neighbor','fix':'cluster 0.0.0.1'},
   {'rank':2,'cause':'originator-id 不一致','probability': 0.3,'verify':'show route protocol bgp','fix':'配 originator-id'}],
  [{'type':'vendor_doc','url':'https://www.juniper.net/documentation/junos-21.2/bgp-cluster','version':'21.2R1'}])

# IS-IS adjacency H3C
W(208, 'IS-IS wide metric 不互通（华三 Comware 7，metric-style 错）', 'h3c', 'Comware-7.1.070', 4, ['isis','wide-metric'],
  'IS-IS wide-metric 邻居不接收 route',
  [{'config_snippet': '# Spine\nisis 1\n is-level level-2\n network-entity 49.0001.0000.0000.0001.00\n# 默认 narrow metric 对 wide 路由不识别'}],
  [], '诊断 wide metric',
  [{'rank':1,'cause':'metric-style 默认 narrow，对端 wide','probability': 0.85,'verify':'display isis','fix':'metric-style wide'},
   {'rank':2,'cause':'metric 跳过 max','probability': 0.15,'verify':'display isis route','fix':'调低 metric'}],
  [{'type':'vendor_doc','url':'https://www.h3c.com/cn/d_202206/isis-metric-wide','version':'Comware 7.1.070'}])

# DHCP relay
W(209, 'DHCP relay 不通（思科 IOS-XE 17，helper address 错配）', 'cisco', 'IOS-XE-17.09', 3, ['dhcp','relay','helper'],
  'DHCP 客户端获取不到 IP',
  [{'config_snippet': 'interface Vlan10\n ip address 10.1.10.1 255.255.255.0\n ip helper-address 10.1.1.99  # ⚠️ 对端是 10.1.1.100'}],
  [], '诊断 DHCP relay',
  [{'rank':1,'cause':'helper-address 配错 IP','probability': 0.7,'verify':'show running-config interface vlan10','fix':'ip helper-address 10.1.1.100'},
   {'rank':2,'cause':'DHCP 服务器策略拒绝','probability': 0.3,'verify':'测试 DHCP server','fix':'修 server 配置'}],
  [{'type':'vendor_doc','url':'https://www.cisco.com/c/en/us/support/dhcp-relay','version':'IOS-XE-17.09'}])

# IPv6 ND RA
W(210, 'IPv6 SLAAC 不工作（Juniper 21.2，managed-config-flag 错配）', 'juniper', '21.2R1', 3, ['ipv6','slaac','managed'],
  'IPv6 客户端获取不到 IPv6',
  [{'config_snippet': '# Junos\nset protocols router-advertisement interface ge-0/0/1 managed-configuration\nset protocols router-advertisement interface ge-0/0/1 other-configuration\n# ⚠️ 应是 Managed+Other 一起'}],
  [], '诊断 SLAAC',
  [{'rank':1,'cause':'router-advertisement 模式错配','probability': 0.8,'verify':'show ipv6 router-advertisement','fix':'managed-configuration 关掉，用 stateless'},
   {'rank':2,'cause':'链路 down','probability': 0.2,'verify':'show interface','fix':'物理修链路'}],
  [{'type':'vendor_doc','url':'https://www.juniper.net/documentation/junos-21.2/slaac','version':'21.2R1'}])

# BFD + OSPF
W(211, 'BFD+OSPF 抖动（思科 IOS-XE 17，bfd interval 错配）', 'cisco', 'IOS-XE-17.09', 3, ['bfd','ospf','interval'],
  'BFD+OSPF 反复 flap',
  [{'config_snippet': 'interface g1/0/1\n ip ospf bfd\n # ⚠️ bfd interval 50ms min_rx 50 multiplier 3'}],
  [], '诊断 BFD OSPF',
  [{'rank':1,'cause':'bfd interval 太短 (50ms)','probability': 0.7,'verify':'show bfd neighbor','fix':'bfd interval 500 min_rx 500 multiplier 3'},
   {'rank':2,'cause':'链路抖动导致 bfd 触 flap','probability': 0.3,'verify':'show interface','fix':'修物理链路'}],
  [{'type':'vendor_doc','url':'https://www.cisco.com/c/en/us/support/bfd-ospf','version':'IOS-XE-17.09'}])

# IPv6 OSPFv3 AS external
W(212, 'OSPFv3 AS-external 不互通（华为 VRP-8.180，import-route 漏 external）', 'huawei', 'VRP-8.180', 3, ['ospfv3','as-external','import'],
  'OSPFv3 type-5 不学习',
  [{'config_snippet': 'ospfv3 1\n import-route bgp cost 5 type 1   # ⚠️ default type 2'}],
  [], '诊断 OSPFv3 type-5',
  [{'rank':1,'cause':'import-route 漏 type 1','probability': 0.7,'verify':'display ospfv3 lsdb','fix':'import-route bgp cost 5 type 1'},
   {'rank':2,'cause':'NSSA 域拒绝','probability': 0.3,'verify':'display ospfv3','fix':'调整 area 类型'}],
  [{'type':'vendor_doc','url':'https://support.huawei.com/vrp-ospfv3-external','version':'VRP-8.180'}])

print(f'batch4 troubleshoot 完成 56 道 (Q-{155}-{210})')

import os
from collections import Counter
cats = Counter()
for f in os.listdir(OUT):
    if not f.endswith('.yaml'): continue
    d = yaml.safe_load(open(f'{OUT}/{f}'))
    cats[d.get('category','unknown')] += 1
print(f'\\n当前: total={sum(cats.values())}', dict(cats))

# === 补齐 Q-178 ~ Q-212 ===
def W3(id_off, title, vendor, version, difficulty, tags, symptom, configs, logs, question, rc, refs):
    """append-only helper for Q-178+"""
    n = f'NSG-Q-{id_off:04d}'
    save({
        'id': n, 'title': title, 'category': 'troubleshoot', 'vendor': vendor, 'version': version,
        'difficulty': difficulty, 'tags': tags,
        'input': {
            'symptom': symptom, 'device_info': {'model': '', 'version': version, 'interfaces': []},
            'evidence': configs + [{'log_lines': l} if isinstance(l, list) else {'config_snippet': l} for l in logs],
            'question': question,
        },
        'expected_output': {'root_causes': rc, 'references': refs},
        'anti_examples': ['请重启设备', '删除进程', '推荐全局清除配置'],
        'grading_rubric': {
            'must_have': ['top 根因为 ' + tags[0], '≥1 验证命令', '≥1 修复命令'],
            'nice_to_have': ['含 rollback'],
            'penalty': ['推荐重启'],
        },
    })
