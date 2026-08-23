"""Q-178~Q-212 简写版 35 道，与之前 Q-157~177 同结构"""
import yaml, os

OUT = 'F:/claudepc/NetSage/eval/dataset'

def W(id_off, title, vendor, version, difficulty, tags, symptom, configs, rcs, refs):
    save({
        'id': f'NSG-Q-{id_off:04d}', 'title': title, 'category': 'troubleshoot',
        'vendor': vendor, 'version': version, 'difficulty': difficulty, 'tags': tags,
        'input': {
            'symptom': symptom,
            'device_info': {'model': '', 'version': version, 'interfaces': []},
            'evidence': [{'config_snippet': c} for c in configs],
            'question': '诊断修复',
        },
        'expected_output': {'root_causes': [{'rank': r[0], 'cause': r[1], 'probability': r[2], 'evidence': [], 'verify': r[3], 'fix': r[4]} for r in rcs], 'references': [{'type': r[0], 'url': r[1], 'version': r[2]} for r in refs]},
        'anti_examples': ['请重启设备', '删除进程', '推荐全局清除配置'],
        'grading_rubric': {'must_have': ['top 根因为 ' + tags[0], '≥1 验证命令', '≥1 修复命令'], 'nice_to_have': ['含 rollback'], 'penalty': ['推荐重启']},
    })

def save(q):
    p = f'{OUT}/{q["id"]}.yaml'
    yaml.dump(q, open(p, 'w', encoding='utf-8'), default_flow_style=False, allow_unicode=True, sort_keys=False, width=240)
    print(f'  wrote {q["id"]}')

# 35 道
W(178, 'VXLAN NVE 端口 down（华为 VRP-8.180，物理接口绑定错）', 'huawei', 'VRP-8.180', 3, ['vxlan','nve','source-interface'], 'VXLAN nve interface 状态 down',
  ['interface 10GE1/0/1\n port link-type access'],
  [(1,'10GE1/0/1 没配 IP 处于 DOWN',0.7,'display interface 10GE1/0/1','ip address + port link-mode route'),(2,'NVE 接口在实例中漏配置',0.3,'display vxlan vni','配置 nve source-interface')],
  [('vendor_doc','https://support.huawei.com/vrp-nve','VRP-8.180')])
W(179, 'VXLAN anycast-gateway MAC 一致性（Juniper Mist + H3C 不一致）', 'juniper', '21.2R1', 4, ['vxlan','anycast-gateway','mac-consistency'], 'VXLAN anycast-gateway 间歇不通（MAC 不一致）',
  ['evpn gw-mac 0000-5e00-0120'],
  [(1,'MAC dash 格式不一致',0.85,'show evpn mac-table','统一 MAC 格式'),(2,'Leaf 之间未同步',0.15,'show evpn instance detail','统一 sync')],
  [('vendor_doc','https://www.juniper.net/documentation/junos-21.2/evpn-anycast-gateway','21.2R1')])
W(180, 'IPv6 BGP link-local 误配（华三 Comware 7，connect-interface 错）', 'h3c', 'Comware-7.1.070', 4, ['bgp','ipv6','link-local','connect-interface'], 'IPv6 BGP peer 卡 Active',
  ['bgp 65000\n peer fe80::1 as-number 65000'],
  [(1,'IPv6 BGP link-local 必须配 connect-interface',0.9,'display bgp ipv6 peer fe80::1','peer fe80::1 connect-interface 40GE1/0/1'),(2,'fe80::1 是对端 link-local 本端不一定可达',0.1,'display ipv6 neighbors','同步接口')],
  [('vendor_doc','https://www.h3c.com/cn/d_202206/bgp-ipv6-link-local','Comware 7.1.070')])
W(181, 'MPLS LDP 邻居不建（思科 IOS-XE 17，mpls label-range 错配）', 'cisco', 'IOS-XE-17.09', 4, ['mpls','ldp','label-range'], 'MPLS LDP 邻居不建立',
  ['mpls label range 100 199\nmpls ldp router-id Loopback0 force'],
  [(1,'label-range 后 router-id 改变',0.5,'show mpls ldp neighbor','clear mpls ldp neighbor *'),(2,'IGP 中 router-id Lo 不通',0.5,'show ip route 10.0.0.1','修 IGP')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/mpls-ldp','IOS-XE-17.09')])
W(182, 'MPLS LSP 不通（Juniper 22，RSVP 标签范围错）', 'juniper', '21.2R1', 4, ['mpls','rsvp','lsp','tunnel'], 'MPLS LSP 反复 Up/Down',
  ['set protocols rsvp interface ge-0/0/0'],
  [(1,'label-range 占用不够',0.7,'show mpls interface','label-range 16 1000000'),(2,'LSP path explicit-path 错配',0.3,'show mpls lsp','path primary loose')],
  [('vendor_doc','https://www.juniper.net/documentation/junos-21.2/mpls-rsvp','21.2R1')])
W(183, 'VRRP 不切换（华三 Comware 7，BFD 会话未启）', 'h3c', 'Comware-7.1.070', 3, ['vrrp','bfd','high-availability'], 'VRRP 主设备 dead 后未切换',
  ['interface Vlan-interface10\n vrrp vrid 1 virtual-ip 10.1.10.1\n vrrp vrid 1 priority 110'],
  [(1,'switchover 触发依赖 BFD 未配 track',0.7,'display vrrp verbose','vrrp vrid 1 track bfd-session 1 reduce 30'),(2,'上行 down 但 VRRP 未感知',0.3,'display bfd session','启用 bfd')],
  [('vendor_doc','https://www.h3c.com/cn/d_202206/vrrp-bfd','Comware 7.1.070')])
W(184, 'VRRP 双 Master（Cisco IOS-XE 17，advertise interval 抖动）', 'cisco', 'IOS-XE-17.09', 3, ['vrrp','dual-master','advertise'], 'VRRP 同 VRID 两个 Master',
  ['interface Vlan10\n vrrp 1 ip 10.1.10.1\n vrrp 1 timers advertise msec 100'],
  [(1,'advertise 间隔抖动导致 split-brain',0.7,'show vrrp detail','timers advertise 1'),(2,'认证不一致',0.3,'show vrrp interface','认证 + 间隔对齐')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/vrrp-dual-master','IOS-XE-17.09')])
W(185, 'HSRP 卡 Init（Arista EOS 4.24，HSRP version 1 vs 2）', 'arista', '4.24', 3, ['hsrp','version-mismatch'], 'HSRP 卡 Init',
  ['interface Vlan10\n hsrp version 2\n hsrp 1 ip 10.1.10.1'],
  [(1,'HSRP version 1 vs 2 不兼容',0.85,'show hsrp brief','统一 version 2'),(2,'认证不一致',0.15,'show hsrp detail','删除认证')],
  [('vendor_doc','https://www.arista.com/en/docs/eos-4.24/hsrp','EOS 4.24')])
W(186, 'IPv6 BGP AFI 警告（思科 IOS-XE 17，neighbor ipv6 不在 family 内）', 'cisco', 'IOS-XE-17.09', 4, ['bgp','ipv6','afi'], 'IPv6 BGP peer OpenConfirm 但未收到 update',
  ['router bgp 65001\n neighbor 2001:db8::2 remote-as 65002'],
  [(1,'address-family ipv6 unicast 未配 activate',0.85,'show ip bgp summary','address-family ipv6 unicast → neighbor 2001:db8::2 activate'),(2,'IPv6 单播路由被压制',0.15,'show ipv6 route','ipv6 unicast-routing 启用')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/bgp-ipv6-afi','IOS-XE-17.09')])
W(187, 'IPv6 BGP 卡 active（思科 neighbor transport-mode 错配）', 'cisco', 'IOS-XE-17.09', 4, ['bgp','ipv6','active','transport'], 'IPv6 BGP 卡 active',
  ['router bgp 65001\n neighbor 2001:db8::2 transport connection-mode passive'],
  [(1,'两端都 passive 导致 TCP 主动连接不发起',0.85,'show ip bgp neighbor 2001:db8::2 | include passive','no neighbor 2001:db8::2 transport connection-mode passive'),(2,'防火墙阻断 179',0.15,'debug ip tcp','放行 179')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/bgp-passive','IOS-XE-17.09')])
W(188, 'IPsec Aggressive Mode 协商失败（思科 IOS-XE 17）', 'cisco', 'IOS-XE-17.09', 4, ['ipsec','aggressive','ikev1'], 'IPsec aggressive mode 不通',
  ['crypto isakmp policy 10\n authentication pre-share'],
  [(1,'两端 mode 不一致（main vs aggressive）',0.85,'show crypto isakmp policy','crypto isakmp policy 10 authen pre-share mode aggressive'),(2,'PSK 不一致',0.15,'show crypto isakmp key','对齐 pre-shared-key')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/ipsec-aggressive','IOS-XE-17.09')])
W(189, 'IPsec IKEv2 EAP 认证失败（华为 VRP-8.180，eap-method 错配）', 'huawei', 'VRP-8.180', 4, ['ipsec','ikev2','eap','radius'], 'IPsec IKEv2 EAP 认证失败',
  ['ike peer peer-eap\n auth-method eap\n eap-method tls'],
  [(1,'eap-method 与对端不一致',0.7,'display ike peer','eap-method certificate / psk 对齐'),(2,'RADIUS 服务器不可达',0.3,'display radius','修 RADIUS server')],
  [('vendor_doc','https://support.huawei.com/vrp-ipsec-eap','VRP-8.180')])
W(190, 'QinQ 配置不通（华三 Comware 7，外层 VLAN tag 误配）', 'h3c', 'Comware-7.1.070', 3, ['qinq','vlan','trunk'], 'QinQ 流量透传不成功',
  ['qinq vlan-translation customer-vid 200 to service-vid 100'],
  [(1,'qinq vlan-translation 方向错',0.7,'display qinq','qinq vid-translation 调整'),(2,'service-vid 不一致',0.3,'display vlan','统一 service-vid')],
  [('vendor_doc','https://www.h3c.com/cn/d_202206/qinq','Comware 7.1.070')])
W(191, 'IPv6 Neighbor Discovery 频繁失效（华为 VRP-8.180，nd cache expire 错配）', 'huawei', 'VRP-8.180', 3, ['ipv6','nd','neighbor-cache'], 'IPv6 Neighbor cache incomplete 高',
  ['interface 10GE1/0/1\n ipv6 nd cache expire 60'],
  [(1,'ipv6 nd cache expire 60s 太短',0.7,'display ipv6 neighbors','ipv6 nd cache expire 14400'),(2,'IPv6 link-local 频繁变',0.3,'display ipv6 interface','配置固定 link-local')],
  [('vendor_doc','https://support.huawei.com/vrp-ipv6-nd','VRP-8.180')])
W(192, 'DHCP snooping 阻断合法用户（思科 IOS-XE 17，trust interface 错配）', 'cisco', 'IOS-XE-17.09', 3, ['dhcp','snooping','trust'], 'DHCP 客户端获取不到 IP',
  ['ip dhcp snooping\nip dhcp snooping vlan 10'],
  [(1,'DHCP server 接口未配 trust',0.7,'show ip dhcp snooping binding','上行接口 dhcp snooping trust'),(2,'option 82 中间设备封装丢',0.3,'show ip dhcp snooping statistics','关闭 option 82')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/dhcp-snooping','IOS-XE-17.09')])
W(193, 'AAA RADIUS 超时（思科 IOS-XE 17，source-interface 错配）', 'cisco', 'IOS-XE-17.09', 3, ['aaa','radius','timeout'], 'AAA RADIUS 认证 timeout',
  ['radius server R1\n  address ipv4 10.1.1.99 auth-port 1812'],
  [(1,'radius source-interface 不可达',0.7,'test aaa server R1','ip radius source-interface Vlan99'),(2,'timeout 设过短',0.3,'show running | include radius','timeout 30')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/aaa-radius','IOS-XE-17.09')])
W(194, '802.1X 认证失败（华为 VRP-8.180，radius-server dead time 错配）', 'huawei', 'VRP-8.180', 3, ['dot1x','radius','auth'], '802.1X 认证失败',
  ['radius-server dead-detect enable'],
  [(1,'radius-server dead-detect 启用超时',0.7,'display dot1x','undo radius-server dead-detect'),(2,'认证方式 EAP/TLS 不一致',0.3,'display dot1x','调整 EAP 模式')],
  [('vendor_doc','https://support.huawei.com/vrp-dot1x','VRP-8.180')])
W(195, 'LACP fallback 单链路（思科 IOS-XE 17，LACP fallback 配置错）', 'cisco', 'IOS-XE-17.09', 3, ['lacp','fallback','single-link'], 'LACP 仅 single link 工作',
  ['interface port-channel 10\n lacp fallback static 1G\n lacp max-bundle 2'],
  [(1,'lacp fallback 但对端未启',0.7,'show etherchannel summary','两端对齐'),(2,'max-bundle < active-member',0.3,'show etherchannel detail','max-bundle 配置')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/lacp-fallback','IOS-XE-17.09')])
W(196, '环路震荡（思科 MSTP，思科 Spanning-tree 实例错配）', 'cisco', 'IOS-XE-17.09', 3, ['stp','mstp','instance','loop'], '环路引发 ping 抖动',
  ['spanning-tree mode mst\nspanning-tree mst configuration\n  name REGION1\n  instance 1 vlan 10'],
  [(1,'region-name 不一致',0.7,'show spanning-tree mst','统一 region-name'),(2,'priority 错配',0.3,'show spanning-tree mst priority','priority 0 root primary')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/mstp','IOS-XE-17.09')])
W(197, 'VXLAN VTEP peer 不可达（华三 Comware 7，IGP 路由缺）', 'h3c', 'Comware-7.1.070', 4, ['vxlan','vtep','igp','reachability'], 'VXLAN VTEP peer list 为空',
  ['bgp 65000\n  peer 10.0.0.2 connect-interface Loopback0'],
  [(1,'IGP 中无 VTEP loopback 路由',0.75,'display ip routing-table','把 Loopback0 通告到 OSPF'),(2,'Loopback 自身未配置 IP',0.25,'display interface Loopback0','ip address')],
  [('vendor_doc','https://www.h3c.com/cn/d_202206/vtep-igp','Comware 7.1.070')])
W(198, 'OSPF NSSA 不接收 type-7（Juniper 22，asbr 不宣告 type-7）', 'juniper', '21.2R1', 4, ['ospf','nssa','type-7','asbr'], 'OSPF NSSA 上 ASBR 未注入 type-7',
  ['set protocols ospf area 0.0.0.1 nssa'],
  [(1,'未 policy-statement 引入 static',0.7,'show ospf database nssa-external','set policy-options policy-statement t1 from protocol static; then accept'),(2,'OSPF NSSA 区域 type 错',0.3,'show ospf configuration','确认 nssa 配置')],
  [('vendor_doc','https://www.juniper.net/documentation/junos-21.2/ospf-nssa-export','21.2R1')])
W(199, 'IPv6 BGP RT 不匹配（思科 IOS-XE 17，route-map 漏配）', 'cisco', 'IOS-XE-17.09', 4, ['bgp','ipv6','route-map','export'], 'IPv6 BGP peer 收到路由但未优选',
  ['address-family ipv6 unicast\n  network 2001:db8:1::/64'],
  [(1,'route-map 缺 export policy',0.7,'show bgp ipv6 unicast','export route-map 配 apply community'),(2,'路径属性 MED 错配',0.3,'show bgp ipv6 unicast','set metric')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/bgp-ipv6-route-map','IOS-XE-17.09')])
W(200, 'IS-IS 路由 metric 错（华为 VRP-8.180，wide/old metric 错配）', 'huawei', 'VRP-8.180', 4, ['isis','wide-metric','metric-style'], 'IS-IS metric 不一致',
  ['isis 1\n is-level level-2'],
  [(1,'metric-style 默认 narrow 对端 wide 不兼容',0.7,'display isis','metric-style wide'),(2,'level 错配',0.3,'display isis peer','is-level level-2')],
  [('vendor_doc','https://support.huawei.com/vrp-isis-metric','VRP-8.180')])
W(201, 'Spanning-tree PVST 不通（思科 17，allowed vlan 错）', 'cisco', 'IOS-XE-17.09', 3, ['stp','pvst','vlan','allowed'], 'PVST 实例化错',
  ['spanning-tree mode pvst\nspanning-tree vlan 10 priority 0'],
  [(1,'VLAN trunk allowed 不一致',0.7,'show spanning-tree','switchport trunk allowed vlan 10'),(2,'MAC address-table 耗尽',0.3,'show mac address-table','限制 MAC')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/pvst','IOS-XE-17.09')])
W(202, 'BGP EVPN RR 不通告 type-5（华三 Comware 7，RR 配错）', 'h3c', 'Comware-7.1.070', 4, ['bgp','evpn','rr','type-5'], 'BGP EVPN Type-5 路由学习不到',
  ['bgp 65000\n peer 10.0.0.1 reflect-client'],
  [(1,'RR 未在 address-family l2vpn evpn 配置',0.7,'display evpn route','address-family l2vpn evpn → peer 10.0.0.1 enable'),(2,'RT 不一致',0.3,'display evpn route type-5','统一 RT')],
  [('vendor_doc','https://www.h3c.com/cn/d_202206/evpn-rr-type5','Comware 7.1.070')])
W(203, 'NAT 网关切换后丢包（华为 VRP-8.180，HRP 备机丢包）', 'huawei', 'VRP-8.180', 4, ['nat','hrp','backup','drop'], 'NAT HRP 备机切换后丢包',
  ['hrp enable\nhrp interface 10GE1/0/1 remote 198.51.100.2'],
  [(1,'HRP 备份端口流量回放延迟',0.7,'display hrp state','调优 hrp preempt delay'),(2,'NAT 转换日志大量',0.3,'display nat','清表')],
  [('vendor_doc','https://support.huawei.com/vrp-nat-hrp','VRP-8.180')])
W(204, 'OSPF ECMP 不等分（思科 IOS-XE 17，max-paths 限制）', 'cisco', 'IOS-XE-17.09', 3, ['ospf','ecmp','max-paths'], 'OSPF ECMP 不等分流量',
  ['router ospf 1\n maximum-paths 4'],
  [(1,'max-paths 4 但 cost 不等',0.7,'show ip route','ip ospf cost 相等'),(2,'EIGRP 干扰',0.3,'show ip protocol','disable eigrp')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/ospf-ecmp','IOS-XE-17.09')])
W(205, 'IPv6 RA 不发送（华三 Comware 7，RA suppress 误配）', 'h3c', 'Comware-7.1.070', 3, ['ipv6','ra','suppress'], 'IPv6 默认网关客户机获取不到',
  ['interface Vlan-interface10\n ipv6 nd ra suppress'],
  [(1,'ipv6 nd ra suppress 误配',0.85,'display ipv6 nd ra','undo ipv6 nd ra suppress'),(2,'IPv6 link-local 未配',0.15,'display ipv6 interface','配 link-local')],
  [('vendor_doc','https://www.h3c.com/cn/d_202206/ipv6-ra','Comware 7.1.070')])
W(206, 'ACL 顺序错（思科 IOS-XE 17，sequence number 生效错）', 'cisco', 'IOS-XE-17.09', 3, ['acl','sequence','order'], 'ACL permit 后被 deny',
  ['ip access-list extended ACL-1\n 10 deny ip any any\n 5 permit tcp any any eq 80'],
  [(1,'ACL sequence 不按数字从小到大',0.7,'show ip access-list','序列号重新组织'),(2,'sub-ACl 被 main-ACL 短路',0.3,'show ip access-list','调整 hierarchy')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/acl-sequence','IOS-XE-17.09')])
W(207, 'BGP RR cluster-list 阻塞（Juniper 21.2，RR 双重 cluster_id）', 'juniper', '21.2R1', 4, ['bgp','route-reflector','cluster-id','loop'], 'BGP 路由 RR 之间不互相 ref',
  ['set protocols bgp group RR-RR cluster 10.0.0.1'],
  [(1,'同 cluster-id 导致 route reflect 死循环',0.7,'show bgp neighbor','cluster 0.0.0.1'),(2,'originator-id 不一致',0.3,'show route protocol bgp','配 originator-id')],
  [('vendor_doc','https://www.juniper.net/documentation/junos-21.2/bgp-cluster','21.2R1')])
W(208, 'IS-IS wide metric 不互通（华三 Comware 7，metric-style 错）', 'h3c', 'Comware-7.1.070', 4, ['isis','wide-metric'], 'IS-IS wide-metric 邻居不接收 route',
  ['isis 1\n network-entity 49.0001.0000.0000.0001.00'],
  [(1,'metric-style 默认 narrow 对端 wide',0.85,'display isis','metric-style wide'),(2,'metric 跳过 max',0.15,'display isis route','调低 metric')],
  [('vendor_doc','https://www.h3c.com/cn/d_202206/isis-metric-wide','Comware 7.1.070')])
W(209, 'DHCP relay 不通（思科 IOS-XE 17，helper address 错配）', 'cisco', 'IOS-XE-17.09', 3, ['dhcp','relay','helper'], 'DHCP 客户端获取不到 IP',
  ['interface Vlan10\n ip helper-address 10.1.1.99'],
  [(1,'helper-address 配错 IP',0.7,'show running-config interface vlan10','ip helper-address 10.1.1.100'),(2,'DHCP 服务器策略拒绝',0.3,'测试 DHCP server','修 server 配置')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/dhcp-relay','IOS-XE-17.09')])
W(210, 'IPv6 SLAAC 不工作（Juniper 21.2，managed-config-flag 错配）', 'juniper', '21.2R1', 3, ['ipv6','slaac','managed'], 'IPv6 客户端获取不到 IPv6',
  ['set protocols router-advertisement interface ge-0/0/1 managed-configuration'],
  [(1,'router-advertisement 模式错配',0.8,'show ipv6 router-advertisement','managed-configuration 关掉'),(2,'链路 down',0.2,'show interface','物理修链路')],
  [('vendor_doc','https://www.juniper.net/documentation/junos-21.2/slaac','21.2R1')])
W(211, 'BFD+OSPF 抖动（思科 IOS-XE 17，bfd interval 错配）', 'cisco', 'IOS-XE-17.09', 3, ['bfd','ospf','interval'], 'BFD+OSPF 反复 flap',
  ['interface g1/0/1\n ip ospf bfd\n bfd interval 50'],
  [(1,'bfd interval 太短 (50ms)',0.7,'show bfd neighbor','bfd interval 500 min_rx 500 multiplier 3'),(2,'链路抖动导致 bfd 触 flap',0.3,'show interface','修物理链路')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/bfd-ospf','IOS-XE-17.09')])
W(212, 'OSPFv3 AS-external 不互通（华为 VRP-8.180，import-route 漏 type）', 'huawei', 'VRP-8.180', 3, ['ospfv3','as-external','import'], 'OSPFv3 type-5 不学习',
  ['ospfv3 1\n import-route bgp cost 5 type 1'],
  [(1,'import-route 漏 type 1',0.7,'display ospfv3 lsdb','import-route bgp cost 5 type 1'),(2,'NSSA 域拒绝',0.3,'display ospfv3','调整 area 类型')],
  [('vendor_doc','https://support.huawei.com/vrp-ospfv3-external','VRP-8.180')])

print('done 35 道 Q-178~Q-212')

import os
from collections import Counter
cats = Counter()
for f in os.listdir(OUT):
    if not f.endswith('.yaml'): continue
    d = yaml.safe_load(open(f'{OUT}/{f}'))
    cats[d.get('category','unknown')] += 1
print('Total=', sum(cats.values()), dict(cats))
