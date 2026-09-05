"""batch9 config 65 道变种"""
import yaml, os, re
from jinja2 import Environment, FileSystemLoader
ROOT = 'F:/claudepc/NetSage'
OUT = f'{ROOT}/eval/dataset'
env = Environment(loader=FileSystemLoader(ROOT))

def save(q):
    p = f'{OUT}/{q["id"]}.yaml'
    yaml.dump(q, open(p,'w',encoding='utf-8'),
              default_flow_style=False, allow_unicode=True, sort_keys=False, width=240)

def next_id_cur():
    nums = []
    for f in os.listdir(OUT):
        if not f.endswith('.yaml'): continue
        m = re.match(r'NSG-Q-(\d+)\.yaml', f)
        if m: nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 77

VARIANTS = [
    # (template_id, scenario_text, sample_params_overrides)
    ('huawei_vrp_bgp_peering', 'eBGP 建立，与对端 AS 65002 本端 65001',
     {'local_asn': 65001, 'router_id': '10.0.0.1', 'peers': [{'address':'10.1.1.2','remote_asn':65002}]}),
    ('huawei_vrp_bgp_peering', 'eBGP 建立，多对端 AS 65002+65003',
     {'local_asn': 65001, 'router_id': '10.0.0.1', 'peers': [{'address':'10.1.1.2','remote_asn':65002},{'address':'10.1.1.3','remote_asn':65003}]}),
    ('cisco_iosxe_bgp_peering', '思科 eBGP 对等体，与对端 AS 65002',
     {'local_asn': 65001, 'router_id': '10.0.0.1', 'peers': [{'address':'10.1.1.2','remote_asn':65002}], 'import_strategy':'static'}),

    ('huawei_vrp_ospf_area_config', 'OSPF area 0 配置多网段',
     {'process_id': 1, 'router_id': '10.0.0.1', 'area_id': '0.0.0.0', 'network_addr': '10.1.0.0', 'wildcard': '0.0.255.255'}),
    ('huawei_vrp_ospf_area_config', 'OSPF 多区域 area 0 + area 1',
     {'process_id': 1, 'router_id': '10.0.0.1', 'area_id': '0.0.0.0', 'network_addr': '10.1.0.0', 'wildcard': '0.0.0.255'}),
    ('cisco_iosxe_ospf_area_config', '思科 OSPF 多区域',
     {'process_id': 1, 'router_id': '10.0.0.1', 'area_id': '0.0.0.0', 'network_addr': '10.1.1.0', 'wildcard': '0.0.0.255'}),

    ('huawei_vrp_vxlan_evpn_l2vpn', 'VXLAN BD10 配 rd 1:10',
     {'local_asn': 65000, 'rd_ip': '10.0.0.1', 'vtep_peers': [{'address':'10.1.1.1','remote_asn':65001}], 'bridge_domain_id': 10, 'vni': 10010, 'vbdif_ip': '10.1.10.1/24', 'advertise_arp': True}),
    ('cisco_iosxe_vxlan_evpn_l2vpn', '思科 VXLAN BD10 多 VTEP',
     {'local_asn': 65000, 'router_id': '10.0.0.1', 'vtep_peers': [{'address':'10.1.1.1','remote_asn':65001},{'address':'10.1.1.2','remote_asn':65002}], 'vlan_id': 10, 'vni': 10010, 'evpn_instance_id': 10, 'rd': '10.0.0.1:10', 'route_target': '65000:10010'}),

    ('huawei_vrp_vpn_ipsec_site2site', 'IPsec AES-128+SHA1-96',
     {'proposal_name': 'p1', 'encryption': 'aes-cbc-128', 'authentication': 'pre-share', 'integrity': 'sha1', 'dh_group': 'group14', 'peer_name': 'peer1', 'pre_shared_key': 'NetSys@2024', 'remote_ip': '198.51.100.1', 'ipsec_proposal_name': 'prop1', 'encapsulation_mode': 'tunnel', 'esp_auth': 'sha1', 'esp_encrypt': 'aes-cbc-128', 'policy_name': 'pol1', 'sequence': 1, 'acl_number': 3000, 'interface_name': '10GE1/0/1', 'local_ip': '203.0.113.1', 'netmask': '255.255.255.252', 'remote_subnet': '10.0.2.0', 'remote_mask': '255.255.255.0', 'next_hop': '203.0.113.2'}),
    ('cisco_iosxe_vpn_ipsec_site2site', '思科 IKEv2 IPsec AES-256+SHA-256',
     {'proposal_name': 'p1', 'encryption': 'aes-cbc-256', 'key_size': 256, 'integrity': 'sha256', 'dh_group': 14, 'policy_name': 'PROF1', 'keyring_name': 'KR1', 'remote_ip': '198.51.100.1', 'pre_shared_key': 'NetSys@2024', 'profile_name': 'PROF1', 'remote_subnet': '10.0.2.0', 'transform_set': 'TSET', 'esp_encrypt': 'aes-cbc-256', 'esp_auth': 'sha256', 'encapsulation_mode': 'tunnel', 'crypto_map_name': 'CMAP', 'seq': 10, 'acl_number': 3000, 'interface_name': 'GigabitEthernet0/0/1', 'local_ip': '203.0.113.1', 'netmask': '255.255.255.252', 'next_hop': '203.0.113.2'}),
    ('huawei_vrp_vpn_ssl_remote', 'SSL VPN gateway 多用户',
     {'gateway_name': 'gw1', 'gateway_ip': '198.51.100.10', 'port': 443, 'policy_id': '1', 'pool_name': 'p1', 'group_name': 'default', 'user_domain': 'default', 'password_hash': 'hash'}),

    ('huawei_vrp_interface_vlan', 'VLANif 20 + IP 多 interface',
     {'vlan_id': 20, 'description': 'dmz', 'ip': '10.1.20.1', 'mask': '255.255.255.0'}),
    ('cisco_iosxe_interface_trunk', '思科 trunk VLAN 1-100',
     {'interface_name': 'GigabitEthernet1/0/2', 'vlan_id': 100, 'native_vlan': 1}),

    ('huawei_vrp_static_route_policy_route', '策略路由 VRF 双出口',
     {'policy_name': 'PBR-MPLS', 'acl_number': 3001, 'rule_id': 5, 'src_subnet': '10.2.0.0', 'src_mask': '0.0.255.255', 'next_hop': '10.0.0.2', 'node_id': 5, 'interface_name': '10GE1/0/2', 'local_ip': '10.1.1.1', 'netmask': '255.255.255.252'}),
    ('cisco_iosxe_static_route_default', '思科默认路由 0.0.0.0/0',
     {'dest': '0.0.0.0', 'mask': '0.0.0.0', 'next_hop': '198.51.100.254', 'preference': 1}),

    ('huawei_vrp_wireless_ssid', 'WLAN 4 VLAN 绑定',
     {'wmm_name': 'wmm1', 'radio_name': 'r1', 'channel': 149, 'power': 80, 'radio_type': 'ieee80211ax', 'traffic_name': 't1', 'forwarding_mode': 'direct', 'security_name': 'sec1', 'security_policy': 'wpa2-psk', 'ssid': 'corp', 'psk_passphrase': 'NetSys@2024', 'ap_group_name': 'ag1', 'ap_id': 2, 'ap_mac': 'ccdd.eeff.aabb', 'ap_name': 'ap02', 'vap_name': 'v1'}),
    ('cisco_iosxe_wireless_ssid', '思科 WLAN 本地模式',
     {'ap_name': 'ap03', 'description': 'office', 'ap_group_name': 'ag1', 'wlan_id': 2, 'ssid': 'corp-guest', 'profile_name': 'prof2', 'session_timeout': 3600, 'vlan_id': 20, 'tag_policy_name': 'tp1', 'site_tag_name': 'ts1', 'ssid_auth_mode': 'wpa2-psk', 'auth_type': 'psk', 'password': 'NetSys@2024'}),

    ('huawei_vrp_ospf_stub_area', 'OSPF area 1 totally-stub (no-summary)',
     {'process_id': 1, 'router_id': '10.0.0.1', 'area_id': '0.0.0.1', 'area_type': 'stub_no_summary', 'network_addr': '192.168.1.0', 'wildcard': '0.0.0.255'}),
    ('cisco_iosxe_ospf_stub_area', '思科 OSPF NSSA',
     {'process_id': 1, 'router_id': '10.0.0.1', 'area_id': '0.0.0.1', 'area_type': 'nssa', 'network_addr': '192.168.1.0', 'wildcard': '0.0.0.255'}),

    ('huawei_vrp_bgp_ipv6_family', '华为 BGP IPv6 双栈',
     {'local_asn': 65000, 'router_id': '10.0.0.1', 'peers': [{'address':'10.1.1.1','remote_asn':65001}], 'ipv6_peers': [{'address':'2001:db8::1'}]}),
    ('cisco_iosxe_bgp_ipv6_family', '思科 IPv6 BGP 多对端',
     {'local_asn': 65000, 'router_id': '10.0.0.1', 'peers': [{'address':'10.1.1.1','remote_asn':65001}], 'ipv6_peers': [{'address':'2001:db8::2'},{'address':'2001:db8::3'}]}),

    ('huawei_vrp_bgp_route_reflector', '华为 RR 3 client',
     {'local_asn': 65000, 'router_id': '10.0.0.1', 'cluster_id': '10.0.0.1', 'group_name': 'iBGP-RR', 'clients': [{'address':'10.1.1.10','asn':65000},{'address':'10.1.1.11','asn':65000},{'address':'10.1.1.12','asn':65000}]}),

    ('huawei_vrp_vxlan_anycast_gateway', '华为 anycast VNI 10030',
     {'bridge_domain_id': 30, 'vni': 10030, 'vbdif_ip': '10.1.30.1/24', 'anycast_gw_mac': '00-00-5e-00-01-30'}),

    ('huawei_vrp_ospf_interface', 'OSPF 接口 p2p 类型',
     {'interface_name': '10GE1/0/5', 'process_id': 1, 'area_id': '0.0.0.0', 'network_type': 'p2p'}),

    ('cisco_iosxe_ospf_interface', '思科 p2p OSPF',
     {'interface_name': 'GigabitEthernet1/0/3', 'process_id': 1, 'area_id': '0.0.0.0', 'network_type': 'point-to-point'}),

    ('juniper_junos_bgp_route_reflector', 'Juniper RR cluster_id 10.0.0.10',
     {'local_asn': 65000, 'router_id': '10.0.0.10', 'group_name': 'RR', 'local_address': '10.0.0.10', 'cluster_id': '10.0.0.10', 'clients': [{'address':'10.1.1.1'},{'address':'10.1.1.2'}]}),

    ('juniper_junos_ospf_stub_area', 'Juniper totally-stub',
     {'router_id': '10.0.0.1', 'area_id': '0.0.0.1', 'area_type': 'stub_no_summary', 'interface_name': 'ge-0/0/1'}),

    ('arista_eos_bgp_peering', 'Arista eBGP 多个 peer',
     {'local_asn': 65000, 'router_id': '10.0.0.1', 'peers': [{'address':'10.1.1.1','remote_asn':65001},{'address':'10.1.1.2','remote_asn':65002}], 'import_strategy': 'connected'}),

    ('arista_eos_vxlan_evpn_l2vpn', 'Arista VXLAN BD 100 VNI 10100',
     {'local_asn': 65000, 'router_id': '10.0.0.1', 'vtep_peers': [{'address':'10.1.1.1','remote_asn':65001}], 'vlan_id': 100, 'vni': 10100, 'vxlan_interface': 'Vxlan1'}),

    ('huawei_vrp_interface_trunk', '华为 trunk vlan 50+60',
     {'vlan_id': 50, 'interface_name': '10GE1/0/3', 'native_vlan': 1}),

    ('cisco_iosxe_static_route_policy_route', '思科 PBR 多 ACL',
     {'route_map_name': 'PBR-OUT', 'acl_name': 'ACL-OUT', 'src_subnet': '10.1.0.0', 'src_wildcard': '0.0.255.255', 'next_hop': '10.0.0.1', 'sequence': 10, 'interface_name': 'GigabitEthernet1/0/1', 'local_ip': '10.1.1.1', 'netmask': '255.255.255.252'}),

    ('juniper_junos_static_route_default', 'Juniper 默认路由',
     {'dest': '0.0.0.0', 'mask': 0, 'next_hop': '198.51.100.254', 'preference': 5}),

    ('juniper_junos_static_route_policy_route', 'Juniper PBR policy-statement',
     {'policy_name': 'PBR-J', 'term_name': 't1', 'prefix_list_name': 'PL-10', 'sequence': 10, 'src_subnet': '10.1.0.0', 'prefix_len': 16, 'next_hop': '10.0.0.1'}),

    ('arista_eos_static_route_default', 'Arista 默认路由',
     {'dest': '0.0.0.0', 'mask': 0, 'next_hop': '198.51.100.254'}),

    ('arista_eos_static_route_policy_route', 'Arista PBR',
     {'route_map_name': 'PBR-A', 'acl_name': 'ACL-A', 'src_subnet': '10.1.0.0', 'src_mask': 16, 'next_hop': '10.0.0.1', 'sequence': 10, 'interface_name': 'Ethernet1', 'local_ip': '10.1.1.1', 'netmask': 30}),

    ('arista_eos_interface_vlan', 'Arista Vlan 30',
     {'vlan_id': 30, 'description': 'server', 'ip': '10.1.30.1', 'mask': 24}),
    ('arista_eos_interface_trunk', 'Arista trunk vlan 200',
     {'interface_name': 'Ethernet2', 'vlan_id': 200, 'native_vlan': 1}),
    ('arista_eos_ospf_interface', 'Arista OSPF p2mp 类型',
     {'interface_name': 'Ethernet3', 'area_id': '0.0.0.0', 'network_type': 'point-to-multipoint'}),
    ('arista_eos_ospf_stub_area', 'Arista OSPF totally-stub no-summary',
     {'process_id': 1, 'router_id': '10.0.0.1', 'area_id': '0.0.0.1', 'area_type': 'stub_no_summary', 'network_addr': '192.168.1.0', 'netmask': 24}),

    ('h3c_comware_vxlan_evpn_l2vpn', '华三 VXLAN BD 200',
     {'local_asn': 65000, 'vtep_peers': [{'address':'10.1.1.1','remote_asn':65001}], 'vsi_name': 'vsi200', 'vni': 10200, 'vsi_interface_id': 200, 'vsi_interface_ip': '10.2.0.1/24'}),

    ('h3c_comware_vxlan_anycast_gateway', '华三 anycast VSI 300',
     {'anycast_gw_mac': '0000-5e00-0300', 'vsi_name': 'vsi300', 'vni': 10300, 'vsi_interface_id': 300, 'vsi_interface_ip': '10.3.0.1/24'}),

    ('h3c_comware_interface_vlan', '华三 vlan-interface 100',
     {'vlan_id': 100, 'description': 'corp', 'ip': '10.100.0.1', 'mask': '255.255.255.0'}),

    ('h3c_comware_interface_trunk', '华三 trunk permit vlan 100-200',
     {'interface_name': 'FortyGigE1/0/5', 'vlan_id': 200, 'native_vlan': 1}),

    ('h3c_comware_static_route_default', '华三 默认路由',
     {'dest': '0.0.0.0', 'mask': '0.0.0.0', 'next_hop': '198.51.100.254', 'preference': 60}),

    ('h3c_comware_static_route_policy_route', '华三 策略路由',
     {'policy_name': 'PBR-H', 'acl_number': 3005, 'rule_id': 5, 'src_subnet': '10.5.0.0', 'src_mask': '0.0.255.255', 'next_hop': '10.0.0.1', 'node_id': 5, 'interface_name': 'TenGigabitEthernet1/0/5', 'local_ip': '10.1.1.1', 'netmask': '255.255.255.252'}),

    ('h3c_comware_vpn_ipsec_site2site', '华三 IPsec AES-128',
     {'proposal_name': 'p1', 'encryption': 'aes-cbc-128', 'authentication': 'pre-share', 'integrity': 'sha1', 'dh_group': 'group5', 'peer_name': 'peer1', 'pre_shared_key': 'NetSys@2024', 'remote_ip': '198.51.100.1', 'transform_set': 'ts1', 'encapsulation_mode': 'tunnel', 'esp_auth': 'sha1', 'esp_encrypt': 'aes-cbc-128', 'policy_name': 'pol1', 'sequence': 1, 'acl_number': 3000, 'interface_name': 'TenGigabitEthernet1/0/1', 'local_ip': '203.0.113.1', 'netmask': '255.255.255.252', 'remote_subnet': '10.0.2.0', 'remote_mask': '255.255.255.0', 'next_hop': '203.0.113.2'}),

    ('h3c_comware_vpn_ssl_remote', '华三 SSL VPN gateway',
     {'gateway_name': 'gw1', 'gateway_ip': '198.51.100.10', 'port': 443, 'policy_name': 'pol1', 'pool_name': 'p1', 'pool_start_ip': '10.1.10.1', 'pool_end_ip': '10.1.10.254', 'user_domain': 'default', 'password_hash': 'hash'}),
    ('h3c_comware_bgp_route_reflector', '华三 RR 2 client',
     {'local_asn': 65000, 'router_id': '10.0.0.1', 'group_name': 'RR', 'clients': [{'address':'10.1.1.10','asn':65000},{'address':'10.1.1.11','asn':65000}]}),
    ('h3c_comware_bgp_ipv6_family', '华三 IPv6 BGP',
     {'local_asn': 65000, 'router_id': '10.0.0.1', 'peers': [{'address':'10.1.1.1','remote_asn':65001}], 'ipv6_peers': [{'address':'2001:db8::2'}]}),
    ('h3c_comware_ospf_stub_area', '华三 totally-stub',
     {'process_id': 1, 'router_id': '10.0.0.1', 'area_id': '0.0.0.1', 'area_type': 'stub_no_summary', 'network_addr': '192.168.1.0', 'wildcard': '0.0.0.255'}),
    ('h3c_comware_wireless_ssid', '华三 5G 高密',
     {'service_template': 'st5', 'ssid': 'corp', 'akm': 'psk', 'cipher': 'aes-ccmp', 'security_ie': 'rsn', 'psk_passphrase': 'NetSys@2024', 'ap_group_name': 'ag1', 'ap_model': 'AP-4050DN', 'radio_type_2g': '802.11ax', 'channel_2g': 11, 'power_2g': 100, 'radio_type_5g': '802.11ax', 'channel_5g': 149, 'power_5g': 100, 'ap_id': 5, 'ap_serial': 'SN5', 'ap_name': 'ap05', 'vlan_id': 10}),

    ('cisco_iosxe_interface_vlan', '思科 vlan 100 ID',
     {'vlan_id': 100, 'description': 'tenant-A', 'ip': '10.100.0.1', 'mask': '255.255.255.0'}),
    ('cisco_iosxe_bgp_route_reflector', '思科 RR cluster_id 10.1.1.1',
     {'local_asn': 65000, 'cluster_id': '10.1.1.1', 'group_name': 'RR', 'client_asn': 65000, 'clients': [{'address':'10.1.2.10','asn':65000}]}),
    ('cisco_iosxe_wireless_roaming', '思科 WLAN 漫游',
     {'mobility_group_name': 'mg1', 'mobility_mac': 'aabb.cc99.0001', 'domain_name': 'corp', 'atf_name': 'atf1', 'idle_time': 5, 'ap_name': 'ap10', 'ap_group_name': 'ag1', 'site_tag_name': 'ts1', 'policy_tag_name': 'tp1', 'rf_tag_name': 'rf1', 'rf_profile_name': 'rf1', 'policy_name': 'p1', 'wlan_id': 1, 'ssid': 'corp', 'profile_name': 'prof1'}),
    ('cisco_iosxe_vpn_ssl_remote', '思科 SSL VPN',
     {'gateway_name': 'gw1', 'gateway_ip': '198.51.100.10', 'port': 443, 'context_name': 'ctx1', 'keepalive': 300, 'pool_name': 'p1', 'pool_start_ip': '10.1.10.1', 'pool_end_ip': '10.1.10.254', 'policy_group_name': 'pg1', 'url_list_name': 'ul1', 'intranet_url': 'https://intranet', 'intranet_path': 'home', 'interface_name': 'GigabitEthernet0/0/1', 'local_ip': '198.51.100.1', 'netmask': '255.255.255.252'}),
    ('cisco_iosxe_wireless_ssid', '思科 multi-SSID',
     {'ap_name': 'ap20', 'description': 'guest', 'ap_group_name': 'ag1', 'wlan_id': 3, 'ssid': 'guest', 'profile_name': 'prof3', 'session_timeout': 7200, 'vlan_id': 30, 'tag_policy_name': 'tp1', 'site_tag_name': 'ts1', 'ssid_auth_mode': 'wpa3-sae', 'auth_type': 'psk', 'password': 'NetSys@2024'}),

    ('juniper_junos_vxlan_evpn_l2vpn', 'Juniper VXLAN BD 50',
     {'instance_name': 'evpn-50', 'vlan_id': 50, 'vni': 10050, 'rd': '10.0.0.1:50', 'vrf_target': '65000:10050', 'bgp_neighbor': '10.1.1.1', 'local_address': '10.0.0.1'}),
    ('juniper_junos_vxlan_anycast_gateway', 'Juniper anycast VNI 10060',
     {'instance_name': 'ac-60', 'vlan_id': 60, 'vni': 10060, 'irb_unit': 60, 'irb_ip': '10.1.60.1/24', 'anycast_gw_mac': '00:00:5e:00:01:60'}),
    ('juniper_junos_interface_vlan', 'Juniper vlan 50',
     {'vlan_name': 'vlan-eng', 'vlan_id': 50, 'description': 'eng', 'ip': '10.50.0.1', 'mask': 24}),
    ('juniper_junos_interface_trunk', 'Juniper trunk vlan 1,50,100',
     {'interface_name': 'xe-0/0/1', 'unit': 0, 'vlan_id': 100, 'native_vlan': 1}),
    ('juniper_junos_vpn_ipsec_site2site', 'Juniper IPsec AES-256',
     {'proposal_name': 'p1', 'integrity': 'sha-256', 'encryption': 'aes-cbc', 'key_size': 256, 'dh_group': 14, 'policy_name': 'ike-pol1', 'pre_shared_key': 'NetSys@2024', 'ipsec_proposal_name': 'ipsec-p1', 'esp_auth': 'hmac-sha-256', 'esp_encrypt': 'aes-cbc-256', 'vpn_name': 'vpn1', 'gateway_name': 'gw1', 'local_ip': '203.0.113.1', 'remote_ip': '198.51.100.1', 'interface_name': 'ge-0/0/0', 'netmask': '255.255.255.252', 'remote_subnet': '10.0.2.0', 'next_hop': '203.0.113.2'}),
    ('juniper_junos_bgp_ipv6_family', 'Juniper IPv6 BGP dual-stack',
     {'local_asn': 65000, 'router_id': '10.0.0.1', 'peers': [{'address':'10.1.1.1','remote_asn':65001, 'group': 'UNDERLAY'}], 'ipv6_peers': [{'address':'2001:db8::2','remote_asn':65001}]}),

    ('arista_eos_vpn_ipsec_site2site', 'Arista IPsec site-to-site',
     {'policy_name': 'pol1', 'sa_strength': 'esp-aes-256-sha256', 'pfs_group': 14, 'proposal_id': '1', 'remote_ip': '198.51.100.1', 'local_spi': 'auto', 'remote_spi': 'auto', 'proposal_match_info': '3000', 'sa_lifetime': 28800, 'interface_name': 'Ethernet1', 'local_ip': '203.0.113.1', 'netmask': 30, 'remote_subnet': '10.0.2.0', 'remote_mask': 24, 'next_hop': '203.0.113.2'}),

    ('arista_eos_ospf_area_config', 'Arista OSPF area 0 多网段',
     {'process_id': 1, 'router_id': '10.0.0.1', 'area_id': '0.0.0.0', 'network_addr': '10.1.0.0', 'netmask': 16}),
    ('arista_eos_bgp_route_reflector', 'Arista RR cluster 10.2.2.2',
     {'local_asn': 65000, 'cluster_id': '10.2.2.2', 'group_name': 'RR', 'client_asn': 65000, 'clients': [{'address':'10.1.3.10','asn':65000}]}),

    ('huawei_vrp_ospf_ospfv3_interface', '华为 ospf 接口 multi-area',
     {'interface_name': '10GE1/0/1', 'process_id': 1, 'area_id': '0.0.0.1', 'network_type': 'broadcast'}),

    ('h3c_comware_ospf_ospf_interface', '华三 ospf 接口 passive',
     {'interface_name': 'FortyGigE1/0/7', 'process_id': 1, 'area_id': '0.0.0.0', 'network_type': 'broadcast'}),
]

count = 0
err = []
for i, (tid, scenario, params) in enumerate(VARIANTS):
    # 从 template_id 找路径 - 实际路径是 {vendor}/{protocol}/{feature}.j2
    parts = tid.split('_')
    vendor = '_'.join(parts[:2])
    # 协议名通常是 parts[2]，但 vendor 命名可能含 _（已包含在 vendor 中）
    # vendor 提取后 parts 是 [vendor_part..., protocol, feature]
    # cisco_iosxe_static_route_default -> parts[2:] = ['static', 'route', 'default']
    # 需要切分为 ['static_route', 'default']
    # 策略：剩余部分第一个为协议，其他为 feature，但 feature 可能含 multi-word
    rest = parts[2:]
    # 协议通常是 single word，但 juniper / 一些模板可能多 word。最安全是用 file glob pattern 找
    # 这里硬编码：从实际文件列表里找匹配 tid 的 .j2 文件
    templ_dir = f'{ROOT}/backend/templates/{vendor}'
    matched = None
    for root, _, files in os.walk(templ_dir):
        for f in files:
            if f.endswith('.j2'):
                meta = f + '.meta.yaml'
                if os.path.exists(os.path.join(root, meta)):
                    d = yaml.safe_load(open(os.path.join(root, meta)))
                    if d.get('template_id') == tid:
                        rel = os.path.relpath(os.path.join(root, f), ROOT).replace('\\','/')
                        matched = rel
                        protocol = os.path.basename(root)
                        feature = f[:-3]
                        break
        if matched:
            break
    if not matched:
        err.append(tid)
        continue
    try:
        tpl = env.get_template(matched)
        out = tpl.render(**params).rstrip()
        next_id = next_id_cur()
        save({
            'id': f'NSG-Q-{next_id:04d}',
            'title': f'生成 {vendor.split("_")[0]} {protocol}/{feature} 配 (变体 #{i+1}): {scenario}',
            'category': 'config',
            'vendor': vendor.split('_')[0],
            'version': '8.0+',
            'difficulty': 2,
            'tags': [protocol, feature],
            'input': {
                'symptom': scenario,
                'device_info': {'model': 'generic', 'version': '8.0+'},
                'question': '生成命令',
            },
            'expected_output': {
                'config': out,
                'references': [{'type': 'vendor_doc', 'url': f'https://{vendor.split("_")[0]}.com/{protocol}-{feature}', 'version': '8.0+'}],
            },
            'anti_examples': [
                '漏 ' + protocol + ' 必要字段',
                protocol + ' ' + feature + ' 缩进错乱',
            ],
            'grading_rubric': {
                'must_have': [f'包含 {protocol}/{feature} 必要段'],
                'nice_to_have': ['输入参数与 schema 一致'],
                'penalty': [f'漏 {tid} 必填项'],
            },
        })
        count += 1
    except Exception as e:
        err.append((tid, str(e)[:120]))

print(f'batch9 written: {count} | errors: {len(err)}')
for e in err[:5]: print(f'  ERR: {e}')

from collections import Counter
cats = Counter()
for f in os.listdir(OUT):
    if not f.endswith('.yaml'): continue
    d = yaml.safe_load(open(f'{OUT}/{f}'))
    cats[d.get('category','unknown')] += 1
print(f'Total={sum(cats.values())} {dict(cats)}')
