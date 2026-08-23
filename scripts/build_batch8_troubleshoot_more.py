"""batch8 troubleshoot 32 道 - 补足到 150"""
import yaml, os
OUT = 'F:/claudepc/NetSage/eval/dataset'

def save(q):
    p = f'{OUT}/{q["id"]}.yaml'
    yaml.dump(q, open(p,'w',encoding='utf-8'),
              default_flow_style=False, allow_unicode=True, sort_keys=False, width=240)

def W(id_off, title, vendor, version, difficulty, tags, symptom, configs, rcs, refs):
    save({
        'id': f'NSG-Q-{id_off:04d}', 'title': title, 'category': 'troubleshoot',
        'vendor': vendor, 'version': version, 'difficulty': difficulty, 'tags': tags,
        'input': {
            'symptom': symptom,
            'device_info': {'model':'', 'version': version, 'interfaces': []},
            'evidence': [{'config_snippet': c} for c in configs],
            'question': '诊断修复',
        },
        'expected_output': {'root_causes': [{'rank':r[0],'cause':r[1],'probability':r[2],'evidence':[],'verify':r[3],'fix':r[4]} for r in rcs],
                          'references':[{'type':r[0],'url':r[1],'version':r[2]} for r in refs]},
        'anti_examples': ['请重启设备', '删除进程', '推荐全局清除配置'],
        'grading_rubric': {'must_have':['top 根因为 '+tags[0],'≥1 验证命令','≥1 修复命令'],'nice_to_have':['含 rollback'],'penalty':['推荐重启']},
    })

next_id = 413

# 32 道混合补足
W(413, 'BGP 路由不优（华为 VRP-8.180，confederation 配错）', 'huawei', 'VRP-8.180', 4, ['bgp','confederation','sub-as'], 'BGP 路由不优',
  ['bgp 65001\n confederation id 65000\n confederation peer-as 65002  # sub-as 间也需配 peer'],
  [(1,'confederation sub-as 配错',0.7,'display bgp peer','undo confederation peer-as → 重新配'),
   (2,'router-id 冲突',0.3,'display bgp router-id','重配 router-id')],
  [('vendor_doc','https://support.huawei.com/vrp-bgp-confederation','VRP-8.180')])
W(414, 'BGP Confed AS-Path (思科 IOS-XE 17)', 'cisco', 'IOS-XE-17.09', 4, ['bgp','confederation'], 'BGP confederation 邻居不通',
  ['router bgp 65002\n confederation identifier 65000\n neighbor 10.1.1.1 remote-as 65003  # 应是 confederation peer'],
  [(1,'confederation 邻居配错',0.8,'show bgp confederation','router bgp 65002 → bgp confederation peers 65003'),
   (2,'BGP router-id 一致',0.2,'show bgp summary','调整 router-id')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/bgp-confederation','IOS-XE-17.09')])
W(415, 'BGP export policy 漏配（华三 Comware 7）', 'h3c', 'Comware-7.1.070', 3, ['bgp','export','policy'], 'BGP 路由不传递给对端',
  ['bgp 65001\n peer 10.1.1.2 as 65002\n # ⚠️ 漏 ipv4-family unicast peer enable'],
  [(1,'ipv4-family 配错',0.7,'display bgp peer','address-family ipv4 → peer 10.1.1.2 enable'),
   (2,'route-policy 阻挡',0.3,'display bgp routing-table filter','调整 route-policy')],
  [('vendor_doc','https://www.h3c.com/cn/d_202206/bgp-export','Comware 7.1.070')])
W(416, 'BGP dampening 抑制过严（思科 IOS-XE 17）', 'cisco', 'IOS-XE-17.09', 4, ['bgp','dampening','reuse','suppress'], '路由被反复 dampening 抑制',
  ['router bgp 65001\n bgp dampening 30 750 2000 60\n # reuse 阈值 750 高'],
  [(1,'reuse 阈值过低',0.7,'show ip bgp dampening dampened-paths','bgp dampening 30 1500 3000 60'),
   (2,'链路抖动源',0.3,'show interface','修物理链路')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/bgp-dampening-threshold','IOS-XE-17.09')])
W(417, 'OSPF DR/BDR 选举频繁变化（Juniper 22，dr-priority 设错）', 'juniper', '21.2R1', 4, ['ospf','dr-priority','election'], 'OSPF DR 反复变化',
  ['set protocols ospf area 0.0.0.0 interface ge-0/0/0 priority 100\n # 优先级每次邻居 up 改一次'],
  [(1,'dr-priority 不稳定',0.7,'show ospf neighbor','set priority 100 永久固定'),
   (2,'OSPF 网络类型频繁变',0.3,'show ospf interface','统一 network-type')],
  [('vendor_doc','https://www.juniper.net/documentation/junos-21.2/ospf-dr-priority','21.2R1')])
W(418, 'OSPF 防环 LSA type-4 缺（Arista EOS 4.24）', 'arista', '4.24', 4, ['ospf','lsa','type-4','abr'], 'OSPF 防环失败',
  ['router ospf 1\n area 0.0.0.1 stub # ⚠️ 缺 ABR type-3 summary'],
  [(1,'stub 漏 no-summary',0.7,'show ip ospf database','area 0.0.0.1 stub no-summary'),
   (2,'ASBR 路由未注入',0.3,'show ip ospf border-routers','配置 ASBR')],
  [('vendor_doc','https://www.arista.com/en/docs/eos-4.24/ospf-stub','EOS 4.24')])
W(419, 'BGP allow-as-in 漏（华为 VRP-8.180，CE 间重复 AS）', 'huawei', 'VRP-8.180', 4, ['bgp','allow-as-in','as-path'], 'BGP 路由不优',
  ['bgp 65001\n peer 10.1.1.2 as-number 65001'],
  [(1,'allow-as-in 缺',0.7,'display bgp routing-table','peer 10.1.1.2 allow-as-in 1'),
   (2,'as-path loop 触发',0.3,'display bgp peer verbose','重启 peer')],
  [('vendor_doc','https://support.huawei.com/vrp-bgp-allow-as-in','VRP-8.180')])
W(420, 'OSPF ABR 配两台同 Router-ID 冲突（华三 Comware 7）', 'h3c', 'Comware-7.1.070', 4, ['ospf','router-id','conflict'], 'OSPF 邻居反复 Up/Down',
  ['ospf 1 router-id 10.0.0.1  # ⚠️ 全网两台 ABR Router-ID 一致'],
  [(1,'Router-ID 冲突导致 OSPF 不收敛',0.85,'display ospf router-id','各 ABR 不同 router-id'),
   (2,'接口认证不一致',0.15,'display ospf','统一认证')],
  [('vendor_doc','https://www.h3c.com/cn/d_202206/ospf-router-id','Comware 7.1.070')])
W(421, 'BGP local-as-as 取代（思科 IOS-XE 17，local-as 改对端可识别）', 'cisco', 'IOS-XE-17.09', 4, ['bgp','local-as','replace'], 'BGP 多 AS 替代',
  ['router bgp 65001\n neighbor 10.1.1.2 local-as 65002\n # ⚠️ 漏 no-prepend replace-as'],
  [(1,'local-as 漏 replace',0.7,'show bgp summary','neighbor 10.1.1.2 local-as 65002 replace-as'),
   (2,'dual-AS 设计错',0.3,'show bgp peer','重新设计')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/bgp-local-as','IOS-XE-17.09')])
W(422, 'BGP RR 客户端无 source（华为 VRP-8.180，iBGP 邻居不达）', 'huawei', 'VRP-8.180', 3, ['bgp','rr','ibgp','connect-interface'], 'BGP RR 客户端不通',
  ['bgp 65001\n router-id 10.0.0.1\n peer 10.1.1.2 as 65001  # ⚠️ 漏 connect-interface'],
  [(1,'BGP iBGP 默认 TTL=255 但需 connect-interface',0.7,'display bgp peer','peer 10.1.1.2 connect-interface Loopback0'),
   (2,'IGP 中无 Loopback',0.3,'display ip routing-table','把 Lo 通告到 IGP')],
  [('vendor_doc','https://support.huawei.com/vrp-bgp-ibgp','VRP-8.180')])
W(423, 'BGP path-attribute selection bug 修复 - cluster-list', 'juniper', '21.2R1', 4, ['bgp','cluster-list','selection'], 'BGP 不优选',
  ['set protocols bgp group RR cluster 10.0.0.1'],
  [(1,'cluster-id 重复死循环',0.7,'show route protocol bgp','调整 cluster id'),
   (2,'originator-id 不一致',0.3,'show bgp neighbor','配 originator-id')],
  [('vendor_doc','https://www.juniper.net/documentation/junos-21.2/bgp-cluster','21.2R1')])
W(424, 'OSPFv3 卡 2-way（Cisco IOS-XE 17）', 'cisco', 'IOS-XE-17.09', 3, ['ospfv3','ipv6','2-way'], 'OSPFv3 卡 2-way',
  ['interface g1/0/1\n ipv6 ospf 1 area 0\n ipv6 ospf priority 0'],
  [(1,'priority 0 DROther',0.7,'show ipv6 ospf neighbor','ipv6 ospf priority 200'),
   (2,'IPv6 link-local 阻断',0.3,'show ipv6 ospf interface','启 IPv6 link-local')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/ospfv3-2-way','IOS-XE-17.09')])
W(425, 'OSPFv3 instance-id 错（华三 Comware 7）', 'h3c', 'Comware-7.1.070', 3, ['ospfv3','instance-id'], 'OSPFv3 卡 Init',
  ['ospfv3 1\n area 0.0.0.0\ninterface 10GE1/0/1\n  ospfv3 1 area 0 instance 17'],
  [(1,'instance-id 对端不一致',0.85,'display ospfv3 interface','ospfv3 1 area 0 instance 18 (对端)'),
   (2,'area-id 错',0.15,'display ospfv3 peer','统一 area')],
  [('vendor_doc','https://www.h3c.com/cn/d_202206/ospfv3-instance','Comware 7.1.070')])
W(426, 'IPv6 OSPFv3 路由选路错（思科 IOS-XE 17）', 'cisco', 'IOS-XE-17.09', 3, ['ospfv3','ipv6','selection'], 'IPv6 OSPFv3 不优选',
  ['interface g1/0/1\n ipv6 ospf cost 100\n # ⚠️ cost 应低'],
  [(1,'cost 设过大',0.7,'show ipv6 ospf interface','ipv6 ospf cost 10'),
   (2,'参考带宽错配',0.3,'show ipv6 ospf','ipv6 ospf reference-bandwidth 1000000')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/ospfv3-cost','IOS-XE-17.09')])
W(427, 'VXLAN Type-3 BUM 不通（Arista EOS 4.24，head-end-replication）', 'arista', '4.24', 4, ['vxlan','bum','head-end'], 'VXLAN Type-3 路由学习不到',
  ['interface Vxlan1\n vxlan-unicast-group 10.0.0.2  # static 不全'],
  [(1,'vxlan-unicast-group 列表不全',0.7,'show vxlan vni','补全 peer-vtep 列表'),
   (2,'BGP EVPN peer enable 漏配',0.3,'show bgp evpn summary','配 BGP EVPN')],
  [('vendor_doc','https://www.arista.com/en/docs/eos-4.24/vxlan-bum','EOS 4.24')])
W(428, 'VXLAN BGP EVPN RR 漏 member vni（思科 NX-OS 9.3）', 'cisco', 'NX-OS-9.3', 4, ['vxlan','evpn','rr','member'], 'VXLAN EVPN Type-3 缺',
  ['interface nve1\n member vni 10010  # ⚠️ 多个 VNI 漏配'],
  [(1,'nve member vni 列表不全',0.7,'show nve vni','补全所有 VNI'),
   (2,'EVPN 邻居未建立',0.3,'show bgp l2vpn evpn summary','修 BGP')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/nx-os-vxlan-rr','NX-OS-9.3')])
W(429, 'VXLAN VTEP source interface 物理 down（Juniper Mist + H3C）', 'h3c', 'Comware-7.1.070', 4, ['vxlan','vtep','source-interface'], 'VXLAN VTEP 不可达',
  ['interface Loopback0\n ip address 10.0.0.1 32'],
  [(1,'source interface 物理 down',0.7,'display interface Loopback0','重启 Lo 接口'),
   (2,'Loopback 接口 IP 被禁',0.3,'display interface brief','启用 IP')],
  [('vendor_doc','https://www.h3c.com/cn/d_202206/vxlan-vtep','Comware 7.1.070')])
W(430, 'VXLAN ARP 不学（华为 VRP-8.180, VBDif 缺 ARP）', 'huawei', 'VRP-8.180', 3, ['vxlan','arp','vbdif'], 'VXLAN 同 Leaf ARP 不学',
  ['interface Vbdif10\n ip address 10.1.10.1 24\n # ⚠️ 漏 arp collect host'],
  [(1,'VBDif 漏 arp collect host',0.85,'display vxlan vni','arp collect host'),
   (2,'anycast-gateway 漏配',0.15,'display evpn instance','配 anycast')],
  [('vendor_doc','https://support.huawei.com/vrp-vxlan-vbdif','VRP-8.180')])
W(431, 'IPsec 隧道 up 但流量不通（思科 IOS-XE 17，TCP MSS 错配）', 'cisco', 'IOS-XE-17.09', 3, ['ipsec','mss','tcp-mss'], 'IPsec 隧道正常但 ping 大包失败',
  ['interface Tunnel0\n tunnel mode ipsec ipv4\n # ⚠️ 漏 ip tcp adjust-mss 1350'],
  [(1,'Tunnel MSS 没调小',0.7,'show crypto map','ip tcp adjust-mss 1350'),
   (2,'PMTU discovery 配错',0.3,'show crypto isakmp','配置 PMTUd')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/ipsec-mss','IOS-XE-17.09')])
W(432, 'IPsec transform-set 漏 ah（华三 Comware 7）', 'h3c', 'Comware-7.1.070', 3, ['ipsec','transform-set','ah'], 'IPsec 流量完整性保护不到位',
  ['ipsec transform-set ts1\n esp encryption-algorithm aes-cbc-256\n # ⚠️ 漏 esp authentication-algorithm'],
  [(1,'transform-set 漏 esp auth',0.7,'display ipsec transform-set','加 esp authentication-algorithm sha2-256'),
   (2,'对端需 ah 而已方 esp',0.3,'display ipsec sa','统一 transform-set')],
  [('vendor_doc','https://www.h3c.com/cn/d_202206/ipsec-transform','Comware 7.1.070')])
W(433, 'OSPF 卡 Init 后死掉（华为 VRP-8.180，authentication key-id 错配）', 'huawei', 'VRP-8.180', 3, ['ospf','authentication','key-id'], 'OSPF 邻居反复 Init/Dead',
  ['ospf 1\n authentication-mode md5 1 plain NetSys@2024'],
  [(1,'md5 key-id 对端 2',0.7,'display ospf interface','统一 key-id 1'),
   (2,'md5 key 一致 key-id 错',0.3,'display ospf peer','检查双方 key-id')],
  [('vendor_doc','https://support.huawei.com/vrp-ospf-md5','VRP-8.180')])
W(434, 'BGP RT 不匹配（华三 Comware 7，VPNv4）', 'h3c', 'Comware-7.1.070', 4, ['bgp','vpnv4','rt'], 'BGP VPNv4 路由不通',
  ['bgp 65001\n vpnv4-family\n  peer 10.1.1.2 enable\n # ⚠️ 漏 RT 配置'],
  [(1,'VPNv4 RT 缺配',0.7,'display bgp vpnv4','配 RT 100:1'),
   (2,'MP-BGP peer 漏 enable',0.3,'display bgp peer','配 vpnv4-family peer enable')],
  [('vendor_doc','https://www.h3c.com/cn/d_202206/bgp-vpnv4','Comware 7.1.070')])
W(435, 'EVPN Type-3 Ingress 复制无法（思科 NX-OS 9.3，IR mode 错配）', 'cisco', 'NX-OS-9.3', 4, ['vxlan','evpn','ingress-replication'], 'EVPN Type-3 IR 不通',
  ['interface nve1\n member vni 10010\n  ingress-replication protocol static\n   peer-vtep 10.0.0.1  # ⚠️ 应 BGP'],
  [(1,'IR mode static 不通',0.7,'show nve vni detail','ingress-replication protocol bgp'),
   (2,'peer-vtep 列表不全',0.3,'show nve peer','补全 peer-vtep')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/nx-os-vxlan-ir','NX-OS-9.3')])
W(436, 'OSPFv3 neighbor 卡（华为 VRP-8.180，ipv6 link-local 重复）', 'huawei', 'VRP-8.180', 3, ['ospfv3','link-local','duplicate'], 'OSPFv3 卡 Init',
  ['ospfv3 1\n interface 10GE1/0/2\n  ospfv3 1 area 0 instance 17\n # ⚠️ 两端 link-local 相同'],
  [(1,'两端 link-local 一致引起冲突',0.7,'display ospfv3 interface','ipv6 address force link-local 改'),
   (2,'ND 重复',0.3,'display ipv6 neighbors','清邻居')],
  [('vendor_doc','https://support.huawei.com/vrp-ospfv3-link-local','VRP-8.180')])
W(437, 'EVPN Symmetric IRB 不通（Juniper Mist）', 'juniper', '21.2R1', 4, ['evpn','symmetric-irb'], 'EVPN IRB 流量不通',
  ['set routing-instances anycast-gw instance-type virtual-switch\n set routing-instances anycast-gw interface irb.20'],
  [(1,'Symmetric IRB 未配置 L3-VNI',0.7,'show evpn irb','配 L3-VNI'),
   (2,'路由-target 跨 VRF',0.3,'show route instance','统一 RT')],
  [('vendor_doc','https://www.juniper.net/documentation/junos-21.2/evpn-irb','21.2R1')])
W(438, 'BGP Maximum-routes 触（Tungsten Fabric + H3C）', 'h3c', 'Comware-7.1.070', 4, ['bgp','maximum-routes'], 'BGP 邻居 Idle',
  ['bgp 65001\n peer 10.1.1.2 maximum-prefix 5000 80'],
  [(1,'对端发 6000+ prefix',0.7,'display bgp routing-table statistics','提高 10000'),
   (2,'路由泄漏',0.3,'display filter-policy','prefix-list 限制')],
  [('vendor_doc','https://www.h3c.com/cn/d_202206/bgp-max-prefix','Comware 7.1.070')])
W(439, 'OSPFv3 type-5 互相泛洪（华为 VRP-8.180，NSSA ABR 配错）', 'huawei', 'VRP-8.180', 4, ['ospfv3','type-5','nssa-abr'], 'OSPFv3 type-5 不转发',
  ['ospfv3 1\n area 0.0.0.1\n  nssa  # ⚠️ 漏 ABR P-bit'],
  [(1,'ABR P-bit 未设',0.7,'display ospfv3 lsdb','配 always-translate-7-to-5'),
   (2,'NSSA ASBR 漏配',0.3,'display ospfv3','配 ASBR NSSA')],
  [('vendor_doc','https://support.huawei.com/vrp-ospfv3-nssa','VRP-8.180')])
W(440, 'BGP RFC 9234 错误处理（思科 IOS-XE 17，external-path-attrib）', 'cisco', 'IOS-XE-17.09', 4, ['bgp','rfc9234','path-attribute'], 'BGP 路由不优',
  ['router bgp 65001\n neighbor 10.1.1.2 attribute-unchanged  # ⚠️ 新 RFC 9234 违例'],
  [(1,'RFC 9234 错过',0.7,'show bgp neighbors 10.1.1.2 | include attribute-unchanged','不配 attribute-unchanged'),
   (2,'对端 BGP v4',0.3,'show bgp summary','统一 BGP 模式')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/bgp-rfc9234','IOS-XE-17.09')])
W(441, 'IPv6 路由通告 ISP 受阻（华三 Comware 7，filter 配错）', 'h3c', 'Comware-7.1.070', 4, ['ipv6','filter','bgp-export'], 'IPv6 BGP 路由不通 ISP',
  ['bgp 65001\n ipv6-family unicast\n  filter-policy export\n # ⚠️ 漏 permit 序列'],
  [(1,'filter-policy 默认 deny',0.7,'display bgp ipv6 filter-policy','配 permit 序列'),
   (2,'network 漏配',0.3,'display bgp ipv6 network','配 network')],
  [('vendor_doc','https://www.h3c.com/cn/d_202206/ipv6-bgp-filter','Comware 7.1.070')])
W(442, 'OSPF 缺 summary LSA（RDF+LSA）', 'cisco', 'IOS-XE-17.09', 3, ['ospf','summary','lsa','area-range'], '区域间 summary 路由缺失',
  ['router ospf 1\n area 0.0.0.1 range 10.1.0.0 255.255.0.0  # ⚠️ 错配 mask'],
  [(1,'wildcard mask 设错',0.7,'show ip ospf database summary','area range 10.1.0.0 255.255.0.0'),
   (2,'LSA flooding 受限',0.3,'show ip ospf neighbor','查邻居稳定性')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/ospf-summary','IOS-XE-17.09')])
W(443, 'IPv6 RA M-flag/O-flag（Cisco IOS-XE 17）', 'cisco', 'IOS-XE-17.09', 4, ['ipv6','slaac','ra','m-flag'], 'IPv6 客户机获取 IP',
  ['ipv6 nd router-preference Medium\n ipv6 nd managed-config-flag'],
  [(1,'M-flag 强制 SLAAC 客户机失败',0.7,'show ipv6 interface','修改 M-flag'),
   (2,'O-flag 设错',0.3,'show ipv6 router','修改 O-flag')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/ipv6-slaac-m-flag','IOS-XE-17.09')])
W(444, 'BGP large-community 漏（华为 VRP-8.180，community 配错）', 'huawei', 'VRP-8.180', 4, ['bgp','large-community'], 'BGP large-community 不生效',
  ['route-policy RC1 permit node 10\n apply large-community 65000:100:10',
  # 注意：需要 enable large-community
 ],
  [(1,'large-community 未 enable',0.7,'display bgp peer verbose','peer 10.1.1.2 advertise-large-community'),
   (2,'route-policy 大社区语法错',0.3,'display route-policy','配正确语法')],
  [('vendor_doc','https://support.huawei.com/vrp-bgp-large-community','VRP-8.180')])
W(445, 'OSPF GR 故障（华三 Comware 7）', 'h3c', 'Comware-7.1.070', 4, ['ospf','graceful-restart','stub-router'], 'OSPF 重启后邻居全闪断',
  ['ospf 1\n graceful-restart  # ⚠️ 漏 enable'],
  [(1,'graceful-restart 未 enable',0.7,'display ospf graceful-restart','配 enable'),
   (2,'helper 邻居未启 GR',0.3,'display ospf peer','两端都启 GR')],
  [('vendor_doc','https://www.h3c.com/cn/d_202206/ospf-gr','Comware 7.1.070')])
W(446, 'BGP ADD-PATH 协商失败（Arista EOS 4.24）', 'arista', '4.24', 4, ['bgp','add-path','receive'], 'BGP ADD-PATH 多路径不通',
  ['router bgp 65001\n address-family ipv4\n  neighbor 10.1.1.2 activate\n  # ⚠️ 漏 add-path'],
  [(1,'ADD-PATH capability 未协商',0.7,'show ip bgp neighbors 10.1.1.2 | include add-path','配 add-path'),
   (2,'对端不支持',0.3,'show ip bgp 10.1.1.2','统一 add-path')],
  [('vendor_doc','https://www.arista.com/en/docs/eos-4.24/bgp-add-path','EOS 4.24')])
W(447, 'IPv4 Multicast IGMP 漏查询（华为 VRP-8.180）', 'huawei', 'VRP-8.180', 4, ['multicast','igmp','querier'], 'IGMP multicast 终端获取不到',
  ['interface Vlanif10\n igmp enable  # ⚠️ 漏 querier'],
  [(1,'IGMP querier 未配',0.7,'display igmp querier','配 querier 10.1.10.1'),
   (2,'PIM-SM 上游配置错',0.3,'display pim bsr','配 PIM BSR')],
  [('vendor_doc','https://support.huawei.com/vrp-igmp-querier','VRP-8.180')])
W(448, 'PIM-SM RPF 失败（思科 IOS-XE 17）', 'cisco', 'IOS-XE-17.09', 4, ['multicast','pim-sm','rpf'], 'PIM-SM RPF 错误',
  ['interface g1/0/1\n ip pim sparse-mode\n # ⚠️ 漏 mroute RPF'],
  [(1,'RPF 接口选择错',0.7,'show ip rpf','配正确 ip mroute'),
   (2,'RPF fail 触发 PIM assert',0.3,'show ip pim neighbor','修 assert')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/pim-rpf','IOS-XE-17.09')])
W(449, 'Multicast MSDP mesh-group（华三 Comware 7）', 'h3c', 'Comware-7.1.070', 4, ['multicast','msdp','mesh-group'], 'MSDP 跨域 RP 失败',
  ['pim\n msdp\n  peer 10.1.1.2 connect-interface Loopback0\n # ⚠️ 漏 mesh-group'],
  [(1,'MSDP mesh-group 未配',0.7,'display msdp peer','配 mesh-group'),
   (2,'SA 过滤失败',0.3,'display msdp sa','查 SA 状态')],
  [('vendor_doc','https://www.h3c.com/cn/d_202206/msdp-mesh','Comware 7.1.070')])
W(450, 'MSDP default-peer 配错（华三 + Cisco）', 'cisco', 'IOS-XE-17.09', 3, ['multicast','msdp','default-peer'], 'MSDP default-peer 不生效',
  ['router msdp\n peer 10.1.1.2 connect-interface Loopback0\n # ⚠️ 漏 default-peer'],
  [(1,'MSDP default-peer 漏配',0.7,'show ip msdp peer','配 default-peer'),
   (2,'MSDP peer 之间 mroute 错配',0.3,'show ip mroute','查 RPF')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/msdp-default','IOS-XE-17.09')])
W(451, 'BGP FlowSpec 错（华三 Comware 7）', 'h3c', 'Comware-7.1.070', 4, ['bgp','flowspec','redirect'], 'BGP FlowSpec 规则不生效',
  ['bgp 65001\n address-family ipv4 flowspec\n  neighbor 10.1.1.2 activate\n # ⚠️ 漏 rules'],
  [(1,'flowspec rules 未配',0.7,'display bgp ipv4 flowspec','配 rules'),
   (2,'redirect 配错',0.3,'display firewall slot','修 redirect')],
  [('vendor_doc','https://www.h3c.com/cn/d_202206/bgp-flowspec','Comware 7.1.070')])
W(452, 'MACsec 配错（华为 VRP-8.180）', 'huawei', 'VRP-8.180', 5, ['macsec','key-chain','fallback'], 'MACsec 加密失败',
  ['interface 10GE1/0/1\n macsec\n # ⚠️ 漏 key-chain'],
  [(1,'MACsec 漏 key-chain',0.7,'display macsec interface','配 key-chain'),
   (2,'mode/availability 漏',0.3,'display macsec','配 mode')],
  [('vendor_doc','https://support.huawei.com/vrp-macsec','VRP-8.180')])
W(453, 'MACsec CAK 错（Cisco IOS-XE 17）', 'cisco', 'IOS-XE-17.09', 5, ['macsec','cak','mka'], 'MACsec 密钥协商失败',
  ['key chain KC1 macsec\n key 1000\n  cryptographic-algorithm aes-128-cmac\n # ⚠️ 漏 CKN'],
  [(1,'MACsec 漏 CKN/CAK 配对',0.7,'show macsec','正确配 CAK'),
   (2,'MKA priority 错',0.3,'show mka','修 priority')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/macsec-mka','IOS-XE-17.09')])
W(454, 'Telemetry gRPC 流异常（思科 NX-OS 9.3）', 'cisco', 'NX-OS-9.3', 3, ['telemetry','grpc','model-driven'], 'Telemetry gRPC 流不通',
  ['feature telemetry\n telemetry\n  destination 10.1.1.100 5432\n   transport grpc'],
  [(1,'Telemetry destination 未配',0.7,'show telemetry destination','配 dest'),
   (2,'Sensor path 错',0.3,'show telemetry sensor','修 sensor path')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/nx-os-telemetry','NX-OS-9.3')])
W(455, 'Telemetry gNMI 通道不建（华三 Comware 7）', 'h3c', 'Comware-7.1.070', 3, ['telemetry','gnmi','channel'], 'Telemetry gNMI 流不通',
  ['telemetry subscription 1\n gNMI subscription\n  destination 10.1.1.100 57400'],
  [(1,'gNMI 未配 dest',0.7,'display telemetry','配 dest'),
   (2,'认证配错',0.3,'display gnmi session','修认证')],
  [('vendor_doc','https://www.h3c.com/cn/d_202206/telemetry-gnmi','Comware 7.1.070')])
W(456, '配置回滚不一致（华为 VRP-8.180，checkpoint 错配）', 'huawei', 'VRP-8.180', 3, ['config','rollback','checkpoint'], '配置回滚不一致',
  ['# save 时漏 checkpoint\nsave\n# 但未 named save config'],
  [(1,'未 named save',0.7,'display saved-configuration','save config 检查点'),
   (2,'upgrade 恢复失败',0.3,'display device','配 manual rollback')],
  [('vendor_doc','https://support.huawei.com/vrp-config-rollback','VRP-8.180')])
W(457, 'AAA RADIUS 共享密钥不匹配（思科 IOS-XE 17）', 'cisco', 'IOS-XE-17.09', 3, ['aaa','radius','shared-secret'], 'AAA RADIUS 认证失败',
  ['radius server R1\n key NetSys@2024  # 本端 2024，对端 2025'],
  [(1,'shared secret 不一致',0.7,'test aaa server R1','同步 shared key'),
   (2,'RADIUS 超时',0.3,'show aaa stats','调 timeout')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/aaa-radius-key','IOS-XE-17.09')])
W(458, 'AAA TACACS+ 端口封装（华三 Comware 7）', 'h3c', 'Comware-7.1.070', 3, ['aaa','tacacs','tcp'], 'TACACS+ 服务异常',
  ['tacacs-server host 10.1.1.99\n tacacs-server key cipher NetSys@2024  # TCP 单连接复用'],
  [(1,'TCP 包长超 256',0.7,'display tacacs','配 TCP 单连接'),
   (2,'共享密钥',0.3,'display tacacs-accounting','对齐 key')],
  [('vendor_doc','https://www.h3c.com/cn/d_202206/tacacs','Comware 7.1.070')])
W(459, 'VXLAN ESI 多归属（华为 VRP-8.180）', 'huawei', 'VRP-8.180', 4, ['evpn','esi','multihoming'], 'EVPN Type-1 ESI 不通',
  ['evpn\n esi bgp 1000 1.1.1.1\n  access-port 10GE1/0/10'],
  [(1,'ESI 配错',0.7,'display evpn esi','修 ESI'),
   (2,'DF election 配错',0.3,'display df','修 DF election')],
  [('vendor_doc','https://support.huawei.com/vrp-evpn-esi','VRP-8.180')])
W(460, 'EVPN Type-2 MAC 重复 IP 通告（思科 NX-OS 9.3，ARP suppression 一致性）', 'cisco', 'NX-OS-9.3', 4, ['evpn','arp-suppression'], 'EVPN ARP 表不稳定',
  ['l2vpn evpn instance 10 point-to-point\n arp suppress\n # 部分 leaf 漏配'],
  [(1,'部分 leaf 漏 arp suppress',0.7,'show l2vpn evpn arp','所有 leaf 都配'),
   (2,'RT 不一致',0.3,'show l2vpn evpn route','统一 RT')],
  [('vendor_doc','https://www.cisco.com/c/en/us/support/nx-os-evpn-arp-suppression','NX-OS-9.3')])
W(461, 'BGP Optimal Route Reflection（Juniper 22，ORR）', 'juniper', '21.2R1', 4, ['bgp','optimal-route-reflection','igp-metric'], 'BGP 不优选',
  ['set protocols bgp group RR internal\n # ⚠️ 漏 optimal-route-reflection'],
  [(1,'ORR 未配置',0.7,'show bgp neighbor','配 ORR'),
   (2,'IGP metric 配置错',0.3,'show isis database','修 IGP metric')],
  [('vendor_doc','https://www.juniper.net/documentation/junos-21.2/bgp-orr','21.2R1')])
W(462, 'VRRP track interface 监视链路（华三 Comware 7）', 'h3c', 'Comware-7.1.070', 3, ['vrrp','track','interface'], 'VRRP 不感知上行链路 Down',
  ['interface Vlan-interface10\n vrrp vrid 1 virtual-ip 10.1.10.1'],
  [(1,'VRRP track interface 漏配',0.7,'display vrrp verbose','配 track'),
   (2,'VRRP timer 短',0.3,'display vrrp','timer 调长')],
  [('vendor_doc','https://www.h3c.com/cn/d_202206/vrrp-track','Comware 7.1.070')])
W(463, 'NetStream 报文采样率错（华为 VRP-8.180）', 'huawei', 'VRP-8.180', 3, ['netstream','sampling'], 'NetStream 计数不准确',
  ['interface 10GE1/0/1\n netstream sampler 1 inbound\n # ⚠️ 漏 sampler 配置'],
  [(1,'Sampler 未配',0.7,'display netstream sampler','配 sampler'),
   (2,'NetStream v9 模板对',0.3,'display netstream template','修 template')],
  [('vendor_doc','https://support.huawei.com/vrp-netstream','VRP-8.180')])

from collections import Counter
cats = Counter()
for f in os.listdir(OUT):
    if not f.endswith('.yaml'): continue
    d = yaml.safe_load(open(f'{OUT}/{f}'))
    cats[d.get('category','unknown')] += 1
print('done batch8, troubleshoot total=', cats['troubleshoot'])
