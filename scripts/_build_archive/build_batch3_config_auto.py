"""batch3 config 题自动生成 — 从 80 模板 + jinja2 渲染，得到 80 道 config 题骨架。

每模板：
- vendor / protocol / feature 已知
- input_schema 定义入参（必备字段名+类型）
- 每模板给一组示例入参 → 渲染出 expected_output.config
- question + anti_examples + grading_rubric 自动构造

剩余 70 道变种题加不同的入参变体生成。
"""
import os, yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = 'F:/claudepc/NetSage'
OUT = f'{ROOT}/eval/dataset'

env = Environment(loader=FileSystemLoader(ROOT), undefined=StrictUndefined)

# 80 模板元数据（手动枚举，匹配 batch2 已交付）
# (vendor, protocol, feature, friendly_name, sample_params)
SAMPLE_PARAMS = {
    # bgp (10)
    ('huawei_vrp','bgp','peering'): {'local_asn': 65000, 'router_id': '10.0.0.1', 'peers': [{'address':'10.1.1.1','remote_asn':65001}], 'import_strategy':'direct'},
    ('cisco_iosxe','bgp','peering'): {'local_asn': 65000, 'router_id': '10.0.0.1', 'peers': [{'address':'10.1.1.1','remote_asn':65001}], 'import_strategy':'static'},
    ('h3c_comware','bgp','peering'): {'local_asn': 65000, 'router_id': '10.0.0.1', 'peers': [{'address':'10.1.1.1','remote_asn':65001}], 'import_strategy':'direct'},
    ('juniper_junos','bgp','peering'): {'local_asn': 65000, 'router_id': '10.0.0.1', 'group_name': 'EBGP', 'local_address': '10.0.0.1', 'peers': [{'address':'10.1.1.1','remote_asn':65001,'group':'EBGP'}], 'import_strategy':'static', 'bgp_neighbor': '10.1.1.1'},
    ('arista_eos','bgp','peering'): {'local_asn': 65000, 'router_id': '10.0.0.1', 'peers': [{'address':'10.1.1.1','remote_asn':65001}], 'import_strategy':'static'},

    ('huawei_vrp','bgp','route_reflector'): {'local_asn': 65000, 'router_id': '10.0.0.1', 'cluster_id': '10.0.0.1', 'group_name': 'iBGP-RR', 'clients':[{'address':'10.1.1.10','asn':65000}]},
    ('cisco_iosxe','bgp','route_reflector'): {'local_asn': 65000, 'cluster_id': '10.0.0.1', 'group_name': 'iBGP-RR', 'client_asn': 65000, 'clients':[{'address':'10.1.1.10','asn':65000}]},
    ('h3c_comware','bgp','route_reflector'): {'local_asn': 65000, 'router_id': '10.0.0.1', 'group_name': 'iBGP-RR', 'clients':[{'address':'10.1.1.10','asn':65000}]},
    ('juniper_junos','bgp','route_reflector'): {'local_asn': 65000, 'router_id': '10.0.0.1', 'group_name': 'iBGP-RR', 'local_address': '10.0.0.1', 'cluster_id': '10.0.0.1', 'clients':[{'address':'10.1.1.10'}]},
    ('arista_eos','bgp','route_reflector'): {'local_asn': 65000, 'cluster_id': '10.0.0.1', 'group_name': 'iBGP-RR', 'client_asn': 65000, 'clients':[{'address':'10.1.1.10','asn':65000}]},

    # bgp ipv6_family
    ('huawei_vrp','bgp','ipv6_family'): {'local_asn': 65000, 'router_id': '10.0.0.1', 'peers': [{'address':'10.1.1.1','remote_asn':65001}], 'ipv6_peers':[{'address':'2001:db8::2'}]},
    ('cisco_iosxe','bgp','ipv6_family'): {'local_asn': 65000, 'router_id': '10.0.0.1', 'peers': [{'address':'10.1.1.1','remote_asn':65001}], 'ipv6_peers':[{'address':'2001:db8::2'}]},
    ('h3c_comware','bgp','ipv6_family'): {'local_asn': 65000, 'router_id': '10.0.0.1', 'peers': [{'address':'10.1.1.1','remote_asn':65001}], 'ipv6_peers':[{'address':'2001:db8::2'}]},
    ('juniper_junos','bgp','ipv6_family'): {'local_asn': 65000, 'router_id': '10.0.0.1', 'peers':[{'address':'10.1.1.1','remote_asn':65001,'group':'UNDERLAY'}], 'ipv6_peers':[{'address':'2001:db8::2','remote_asn':65001}]},
    ('arista_eos','bgp','ipv6_family'): {'local_asn': 65000, 'router_id': '10.0.0.1', 'peers': [{'address':'10.1.1.1','remote_asn':65001}], 'ipv6_peers':[{'address':'2001:db8::2'}]},

    # ospf (10)
    ('huawei_vrp','ospf','area_config'): {'process_id':1, 'router_id':'10.0.0.1', 'area_id':'0.0.0.0', 'network_addr':'10.1.1.0', 'wildcard':'0.0.0.255'},
    ('cisco_iosxe','ospf','area_config'): {'process_id':1, 'router_id':'10.0.0.1', 'area_id':'0.0.0.0', 'network_addr':'10.1.1.0', 'wildcard':'0.0.0.255'},
    ('h3c_comware','ospf','area_config'): {'process_id':1, 'router_id':'10.0.0.1', 'area_id':'0.0.0.0', 'network_addr':'10.1.1.0', 'wildcard':'0.0.0.255'},
    ('juniper_junos','ospf','area_config'): {'router_id':'10.0.0.1', 'area_id':'0.0.0.0', 'interface_name':'ge-0/0/0'},
    ('arista_eos','ospf','area_config'): {'process_id':1, 'router_id':'10.0.0.1', 'area_id':'0.0.0.0', 'network_addr':'10.1.1.0', 'netmask':24},

    ('huawei_vrp','ospf','interface'): {'interface_name':'10GE1/0/1', 'process_id':1, 'area_id':'0.0.0.0', 'network_type':'broadcast'},
    ('cisco_iosxe','ospf','interface'): {'interface_name':'GigabitEthernet1/0/1', 'process_id':1, 'area_id':'0.0.0.0', 'network_type':'broadcast'},
    ('h3c_comware','ospf','interface'): {'interface_name':'FortyGigE1/0/1', 'process_id':1, 'area_id':'0.0.0.0', 'network_type':'broadcast'},
    ('juniper_junos','ospf','interface'): {'router_id':'10.0.0.1', 'ls_name':'LS1', 'area_id':'0.0.0.0', 'interface_name':'ge-0/0/0', 'network_type':'broadcast'},
    ('arista_eos','ospf','interface'): {'interface_name':'Ethernet1', 'area_id':'0.0.0.0', 'network_type':'broadcast'},

    ('huawei_vrp','ospf','stub_area'): {'process_id':1, 'router_id':'10.0.0.1', 'area_id':'0.0.0.1', 'area_type':'stub', 'network_addr':'192.168.1.0', 'wildcard':'0.0.0.255'},
    ('cisco_iosxe','ospf','stub_area'): {'process_id':1, 'router_id':'10.0.0.1', 'area_id':'0.0.0.1', 'area_type':'stub', 'network_addr':'192.168.1.0', 'wildcard':'0.0.0.255'},
    ('h3c_comware','ospf','stub_area'): {'process_id':1, 'router_id':'10.0.0.1', 'area_id':'0.0.0.1', 'area_type':'stub', 'network_addr':'192.168.1.0', 'wildcard':'0.0.0.255'},
    ('juniper_junos','ospf','stub_area'): {'router_id':'10.0.0.1', 'area_id':'0.0.0.1', 'area_type':'stub', 'interface_name':'ge-0/0/0'},
    ('arista_eos','ospf','stub_area'): {'process_id':1, 'router_id':'10.0.0.1', 'area_id':'0.0.0.1', 'area_type':'stub', 'network_addr':'192.168.1.0', 'netmask':24},

    # vxlan (10)
    ('huawei_vrp','vxlan','evpn_l2vpn'): {'local_asn':65000, 'rd_ip':'10.0.0.1', 'vtep_peers':[{'address':'10.1.1.1','remote_asn':65001}], 'bridge_domain_id':10, 'vni':10010, 'vbdif_ip':'10.1.10.1/24', 'advertise_arp':True},
    ('cisco_iosxe','vxlan','evpn_l2vpn'): {'local_asn':65000, 'router_id':'10.0.0.1', 'vtep_peers':[{'address':'10.1.1.1','remote_asn':65001}], 'vlan_id':10, 'vni':10010, 'evpn_instance_id':10, 'rd':'10.0.0.1:10', 'route_target':'65000:10010'},
    ('h3c_comware','vxlan','evpn_l2vpn'): {'local_asn':65000, 'vtep_peers':[{'address':'10.1.1.1','remote_asn':65001}], 'vsi_name':'vsi10', 'vni':10010, 'vsi_interface_id':1, 'vsi_interface_ip':'10.1.10.1/24'},
    ('juniper_junos','vxlan','evpn_l2vpn'): {'instance_name':'evpn-10', 'vlan_id':10, 'vni':10010, 'rd':'10.0.0.1:10', 'vrf_target':'65000:10010', 'bgp_neighbor':'10.1.1.1', 'local_address':'10.0.0.1'},
    ('arista_eos','vxlan','evpn_l2vpn'): {'local_asn':65000, 'router_id':'10.0.0.1', 'vtep_peers':[{'address':'10.1.1.1','remote_asn':65001}], 'vlan_id':10, 'vni':10010, 'vxlan_interface':'Vxlan1'},

    ('huawei_vrp','vxlan','anycast_gateway'): {'bridge_domain_id':20, 'vni':10020, 'vbdif_ip':'10.1.20.1/24', 'anycast_gw_mac':'00-00-5e-00-01-20'},
    ('cisco_iosxe','vxlan','anycast_gateway'): {'anycast_gw_mac':'0000.5e00.0120', 'vlan_id':20, 'vni':10020, 'vlanif_ip':'10.1.20.1/24', 'evpn_instance_id':20, 'rd':'10.0.0.1:20', 'route_target':'65000:10020', 'local_asn':65000},
    ('h3c_comware','vxlan','anycast_gateway'): {'anycast_gw_mac':'0000-5e00-0120', 'vsi_name':'vsi20', 'vni':10020, 'vsi_interface_id':2, 'vsi_interface_ip':'10.1.20.1/24'},
    ('juniper_junos','vxlan','anycast_gateway'): {'instance_name':'anycast-gw', 'vlan_id':20, 'vni':10020, 'irb_unit':20, 'irb_ip':'10.1.20.1/24', 'anycast_gw_mac':'00:00:5e:00:01:20'},
    ('arista_eos','vxlan','anycast_gateway'): {'anycast_gw_mac':'00:00:5e:00:01:20', 'vlan_id':20, 'vni':10020, 'vlanif_ip':'10.1.20.1/24', 'vxlan_interface':'Vxlan1', 'local_asn':65000, 'vtep_peers':[{'address':'10.1.1.1','remote_asn':65001}]},

    # vpn (10)
    ('huawei_vrp','vpn','ipsec_site2site'): {'proposal_name':'p1', 'encryption':'aes-cbc-256', 'authentication':'pre-share', 'integrity':'sha2-256', 'dh_group':'group14', 'peer_name':'peer1', 'pre_shared_key':'NetSys@2024', 'remote_ip':'198.51.100.1', 'ipsec_proposal_name':'prop1', 'encapsulation_mode':'tunnel', 'esp_auth':'sha2-256', 'esp_encrypt':'aes-cbc-256', 'policy_name':'pol1', 'sequence':1, 'acl_number':3000, 'interface_name':'10GE1/0/1', 'local_ip':'203.0.113.1', 'netmask':'255.255.255.252', 'remote_subnet':'10.0.2.0', 'remote_mask':'255.255.255.0', 'next_hop':'203.0.113.2'},
    ('cisco_iosxe','vpn','ipsec_site2site'): {'proposal_name':'p1', 'encryption':'aes-cbc-256', 'key_size':256, 'integrity':'sha256', 'dh_group':14, 'policy_name':'ikev2-pol', 'keyring_name':'KR1', 'remote_ip':'198.51.100.1', 'pre_shared_key':'NetSys@2024', 'profile_name':'PROF1', 'remote_subnet':'10.0.2.0', 'transform_set':'TSET', 'esp_encrypt':'aes-cbc-256', 'esp_auth':'sha256', 'encapsulation_mode':'tunnel', 'crypto_map_name':'CMAP', 'seq':10, 'acl_number':3000, 'interface_name':'GigabitEthernet0/0/1', 'local_ip':'203.0.113.1', 'netmask':'255.255.255.252', 'next_hop':'203.0.113.2'},
    ('h3c_comware','vpn','ipsec_site2site'): {'proposal_name':'p1', 'encryption':'aes-cbc-256', 'authentication':'pre-share', 'integrity':'sha2-256', 'dh_group':'group14', 'peer_name':'peer1', 'pre_shared_key':'NetSys@2024', 'remote_ip':'198.51.100.1', 'transform_set':'tset1', 'encapsulation_mode':'tunnel', 'esp_auth':'sha2-256', 'esp_encrypt':'aes-cbc-256', 'policy_name':'pol1', 'sequence':1, 'acl_number':3000, 'interface_name':'TenGigabitEthernet1/0/1', 'local_ip':'203.0.113.1', 'netmask':'255.255.255.252', 'remote_subnet':'10.0.2.0', 'remote_mask':'255.255.255.0', 'next_hop':'203.0.113.2'},
    ('juniper_junos','vpn','ipsec_site2site'): {'proposal_name':'p1', 'integrity':'sha-256', 'encryption':'aes-cbc', 'key_size':256, 'dh_group':14, 'policy_name':'ike-pol1', 'pre_shared_key':'NetSys@2024', 'ipsec_proposal_name':'ipsec-p1', 'esp_auth':'hmac-sha-256', 'esp_encrypt':'aes-cbc-256', 'vpn_name':'vpn1', 'gateway_name':'gw1', 'local_ip':'203.0.113.1', 'remote_ip':'198.51.100.1', 'interface_name':'ge-0/0/1', 'netmask':'255.255.255.252', 'remote_subnet':'10.0.2.0', 'next_hop':'203.0.113.2'},
    ('arista_eos','vpn','ipsec_site2site'): {'policy_name':'pol1', 'sa_strength':'esp-aes-256-sha1', 'pfs_group':14, 'proposal_id':'1', 'remote_ip':'198.51.100.1', 'local_spi':'auto', 'remote_spi':'auto', 'proposal_match_info':'3000', 'sa_lifetime':28800, 'interface_name':'Ethernet1', 'local_ip':'203.0.113.1', 'netmask':30, 'remote_subnet':'10.0.2.0', 'remote_mask':24, 'next_hop':'203.0.113.2'},

    ('huawei_vrp','vpn','ssl_remote'): {'gateway_name':'gw1', 'gateway_ip':'198.51.100.10', 'port':443, 'policy_id':'1', 'pool_name':'p1', 'group_name':'default', 'user_domain':'default', 'password_hash':'hash'},
    ('cisco_iosxe','vpn','ssl_remote'): {'gateway_name':'gw1', 'gateway_ip':'198.51.100.10', 'port':443, 'context_name':'ctx1', 'keepalive':300, 'pool_name':'p1', 'pool_start_ip':'10.1.10.1', 'pool_end_ip':'10.1.10.254', 'policy_group_name':'pg1', 'url_list_name':'ul1', 'intranet_url':'http://intranet', 'intranet_path':'home', 'interface_name':'GigabitEthernet0/0/1', 'local_ip':'198.51.100.1', 'netmask':'255.255.255.252'},
    ('h3c_comware','vpn','ssl_remote'): {'gateway_name':'gw1', 'gateway_ip':'198.51.100.10', 'port':443, 'policy_name':'pol1', 'pool_name':'p1', 'pool_start_ip':'10.1.10.1', 'pool_end_ip':'10.1.10.254', 'user_domain':'default', 'password_hash':'hash'},
    ('juniper_junos','vpn','ssl_remote'): {'profile_name':'ssl1', 'cert_id':'cert1', 'client_name':'c1', 'group_name':'g1', 'password':'pw', 'pool_name':'p1', 'pool_start_ip':'10.1.10.0/24', 'pool_range_low':'10.1.10.1', 'pool_range_high':'10.1.10.254', 'interface_name':'ge-0/0/1', 'aaa_profile_name':'aaa1', 'zone_name':'untrust', 'address_name':'intranet', 'remote_subnet':'10.0.0.0/16', 'trust_zone':'trust', 'policy_name':'pol1'},
    ('arista_eos','vpn','ssl_remote'): {'policy_name':'pol1', 'cipher_list':'AES256-SHA256:ECDHE-RSA-AES256-GCM-SHA384', 'session_cache_timeout':600, 'ssl_profile':'ssl1', 'acl_name':'acl1', 'remote_subnet':'10.0.0.0', 'remote_mask':16, 'auth_policy_name':'auth1', 'rule_id':1, 'user_name':'u1', 'radius_server_name':'r1', 'radius_ip':'10.1.1.99', 'radius_secret':'sec1', 'next_hop':'198.51.100.254'},

    # interface (10)
    ('huawei_vrp','interface','trunk'): {'vlan_id':10, 'interface_name':'10GE1/0/1', 'native_vlan':1},
    ('cisco_iosxe','interface','trunk'): {'interface_name':'GigabitEthernet1/0/1', 'vlan_id':10, 'native_vlan':1},
    ('h3c_comware','interface','trunk'): {'interface_name':'FortyGigE1/0/1', 'vlan_id':10, 'native_vlan':1},
    ('juniper_junos','interface','trunk'): {'interface_name':'ge-0/0/1', 'unit':0, 'vlan_id':10, 'native_vlan':1},
    ('arista_eos','interface','trunk'): {'interface_name':'Ethernet1', 'vlan_id':10, 'native_vlan':1},

    ('huawei_vrp','interface','vlan'): {'vlan_id':10, 'description':'mgmt', 'ip':'10.1.10.1', 'mask':'255.255.255.0'},
    ('cisco_iosxe','interface','vlan'): {'vlan_id':10, 'description':'mgmt', 'ip':'10.1.10.1', 'mask':'255.255.255.0'},
    ('h3c_comware','interface','vlan'): {'vlan_id':10, 'description':'mgmt', 'ip':'10.1.10.1', 'mask':'255.255.255.0'},
    ('juniper_junos','interface','vlan'): {'vlan_name':'vlan-mgmt', 'vlan_id':10, 'description':'mgmt', 'ip':'10.1.10.1', 'mask':24},
    ('arista_eos','interface','vlan'): {'vlan_id':10, 'description':'mgmt', 'ip':'10.1.10.1', 'mask':24},

    # static_route (10)
    ('huawei_vrp','static_route','default'): {'dest':'0.0.0.0', 'mask':'0.0.0.0', 'next_hop':'198.51.100.254', 'preference':60, 'description':'default GW'},
    ('cisco_iosxe','static_route','default'): {'dest':'0.0.0.0', 'mask':'0.0.0.0', 'next_hop':'198.51.100.254', 'preference':1},
    ('h3c_comware','static_route','default'): {'dest':'0.0.0.0', 'mask':'0.0.0.0', 'next_hop':'198.51.100.254', 'preference':60},
    ('juniper_junos','static_route','default'): {'dest':'0.0.0.0', 'mask':0, 'next_hop':'198.51.100.254', 'preference':5},
    ('arista_eos','static_route','default'): {'dest':'0.0.0.0', 'mask':0, 'next_hop':'198.51.100.254'},

    ('huawei_vrp','static_route','policy_route'): {'policy_name':'PBR1', 'acl_number':3000, 'rule_id':10, 'src_subnet':'10.1.0.0', 'src_mask':'0.0.255.255', 'next_hop':'10.0.0.1', 'node_id':10, 'interface_name':'10GE1/0/1', 'local_ip':'10.1.1.1', 'netmask':'255.255.255.252'},
    ('cisco_iosxe','static_route','policy_route'): {'route_map_name':'PBR1', 'acl_name':'ACL-PBR', 'src_subnet':'10.1.0.0', 'src_wildcard':'0.0.255.255', 'next_hop':'10.0.0.1', 'sequence':10, 'interface_name':'GigabitEthernet1/0/1', 'local_ip':'10.1.1.1', 'netmask':'255.255.255.252'},
    ('h3c_comware','static_route','policy_route'): {'policy_name':'PBR1', 'acl_number':3000, 'rule_id':10, 'src_subnet':'10.1.0.0', 'src_mask':'0.0.255.255', 'next_hop':'10.0.0.1', 'node_id':10, 'interface_name':'TenGigabitEthernet1/0/1', 'local_ip':'10.1.1.1', 'netmask':'255.255.255.252'},
    ('juniper_junos','static_route','policy_route'): {'policy_name':'PBR1', 'term_name':'t1', 'prefix_list_name':'PL-10', 'sequence':10, 'src_subnet':'10.1.0.0', 'prefix_len':16, 'next_hop':'10.0.0.1'},
    ('arista_eos','static_route','policy_route'): {'route_map_name':'PBR1', 'acl_name':'ACL-PBR', 'src_subnet':'10.1.0.0', 'src_mask':16, 'next_hop':'10.0.0.1', 'sequence':10, 'interface_name':'Ethernet1', 'local_ip':'10.1.1.1', 'netmask':30},

    # wireless (6)
    ('huawei_vrp','wireless','ssid'): {'wmm_name':'wmm1', 'radio_name':'r1', 'channel':36, 'power':50, 'radio_type':'ieee80211ax', 'traffic_name':'t1', 'forwarding_mode':'direct', 'security_name':'sec1', 'security_policy':'wpa2-psk', 'ssid':'corp', 'psk_passphrase':'Pass@2024', 'ap_group_name':'ag1', 'ap_id':1, 'ap_mac':'aabb.ccdd.eeff', 'ap_name':'ap01', 'vap_name':'v1'},
    ('cisco_iosxe','wireless','ssid'): {'ap_name':'ap01', 'description':'office', 'ap_group_name':'ag1', 'wlan_id':1, 'ssid':'corp', 'profile_name':'prof1', 'session_timeout':1800, 'vlan_id':10, 'tag_policy_name':'tp1', 'site_tag_name':'ts1', 'ssid_auth_mode':'wpa2-psk', 'auth_type':'psk', 'password':'Pass@2024'},
    ('h3c_comware','wireless','ssid'): {'service_template':'st1', 'ssid':'corp', 'akm':'psk', 'cipher':'aes-ccmp', 'security_ie':'rsn', 'psk_passphrase':'Pass@2024', 'ap_group_name':'ag1', 'ap_model':'AP-9150', 'radio_type_2g':'802.11ax', 'channel_2g':6, 'power_2g':50, 'radio_type_5g':'802.11ax', 'channel_5g':36, 'power_5g':50, 'ap_id':1, 'ap_serial':'SN123', 'ap_name':'ap01', 'vlan_id':10},
    ('juniper_junos','wireless','ssid'): {'org_id':'org-1', 'site_id':'site-1', 'ssid':'corp', 'vlan_id':10, 'psk_passphrase':'Pass@2024', 'bands':['2.4','5'], 'isolation':True},
    ('arista_eos','wireless','ssid'): {'profile_name':'prof1', 'ssid_name':'ssid-corp', 'ssid':'corp', 'vlan_id':10, 'psk_passphrase':'Pass@2024', 'channel_2g':6, 'power_2g':50, 'channel_5g':36, 'power_5g':50, 'ap_group_name':'ag1', 'ap_model':'W-118', 'ap_mac':'aabb.ccdd.eeff', 'ap_name':'ap01'},
    ('huawei_vrp','wireless','roaming'): {'wlan_group_name':'wg1', 'roaming_mode':'enable', 'mobility_group':'mg1', 'domain_name':'dom1', 'ap_group_name':'ag1', 'channel_24':6, 'power_24':50, 'channel_5':36, 'power_5':50, 'ap_mac':'aabb.ccdd.eeff', 'ap_name':'ap01', 'security_name':'sec1', 'psk_passphrase':'Pass@2024', 'ssid_profile_name':'sp1', 'ssid':'corp', 'vap_name':'v1'},
    ('cisco_iosxe','wireless','roaming'): {'mobility_group_name':'mg1', 'mobility_mac':'aabb.ccdd.0001', 'domain_name':'dom1', 'atf_name':'atf1', 'idle_time':5, 'ap_name':'ap01', 'ap_group_name':'ag1', 'site_tag_name':'ts1', 'policy_tag_name':'tp1', 'rf_tag_name':'rf1', 'rf_profile_name':'rf1', 'policy_name':'p1', 'wlan_id':1, 'ssid':'corp', 'profile_name':'prof1'},
    ('h3c_comware','wireless','roaming'): {'mobility_group_name':'mg1', 'domain_name':'dom1', 'member_ip':'10.1.2.1', 'reauth_timeout':60, 'roam_leverage':5, 'ap_group_name':'ag1', 'roam_threshold':-65, 'sticky_threshold':-75, 'ap_id':1, 'ap_serial':'SN123', 'ap_name':'ap01'},
    ('juniper_junos','wireless','roaming'): {'org_id':'org-1', 'site_id':'site-1', 'mobility_domain':'aabb', 'method':'ft-over-ds', 'r0_key_timeout':60, 'band_steering':True, 'sticky_rssi':-75},
    ('arista_eos','wireless','roaming'): {'mobility_group_name':'mg1', 'mobility_domain':'aabb', 'sticky_threshold':-75, 'roam_threshold':-65, 'ap_group_name':'ag1', 'ap_mac':'aabb.ccdd.eeff', 'ap_name':'ap01'},
}

def render_template(vendor, protocol, feature):
    j2_path = f'backend/templates/{vendor}/{protocol}/{feature}.j2'
    if not os.path.exists(os.path.join(ROOT, j2_path)):
        return None
    tpl = env.get_template(j2_path)
    params = SAMPLE_PARAMS.get((vendor, protocol, feature), {})
    if not params:
        return None
    try:
        return tpl.render(**params)
    except Exception as e:
        return f'# RENDER ERROR: {str(e)[:200]}'

def find_next_id(start=77):
    """找起始 ID"""
    nums = []
    for f in os.listdir(OUT):
        if not f.endswith('.yaml'): continue
        import re
        m = re.match(r'NSG-Q-(\d+)\.yaml', f)
        if m: nums.append(int(m.group(1)))
    nums.sort()
    return max(start, (nums[-1]+1) if nums else start)

def build_config_q(vendor, protocol, feature, next_id, top_question):
    rendered = render_template(vendor, protocol, feature)
    if not rendered:
        return None
    meta = yaml.safe_load(open(f'{ROOT}/backend/templates/{vendor}/{protocol}/{feature}.j2.meta.yaml'))
    vendor_name = {'huawei_vrp':'huawei','cisco_iosxe':'cisco','h3c_comware':'h3c','juniper_junos':'juniper','arista_eos':'arista'}[vendor]
    # Mist API 不适合 config 题
    if meta.get('output_format') == 'api':
        return None
    return {
        'id': f'NSG-Q-{next_id:04d}',
        'title': f'生成 {vendor_name} {protocol}/{feature} 配置 ({top_question})',
        'category': 'config',
        'vendor': vendor_name,
        'version': meta.get('version_min','8.0')+'+',
        'difficulty': 2,
        'tags': [protocol, feature],
        'input': {
            'symptom': top_question,
            'device_info': {'model': 'generic', 'version': meta.get('version_min','8.0')+'+'},
            'question': '生成命令',
        },
        'expected_output': {
            'config': rendered,
            'references': [{'type':'vendor_doc','url': f'https://support.{vendor_name}.com/{protocol}-{feature}','version': meta.get('version_min','8.0')}],
        },
        'anti_examples': [
            f'漏 {protocol} 必要字段',
            f'{protocol} {feature} 缩进错乱（应当 {meta.get("output_format","cli")} 风格）',
        ],
        'grading_rubric': {
            'must_have': [f'包含 {protocol}/{feature} 必要段'],
            'nice_to_have': [f'输入参数与 schema 一致'],
            'penalty': [f'漏 {meta.get("template_id")} 必填项'],
        },
    }

# 80 模板的精确枚举：5 vendor × 16 feature（每个 vendor 单独列举）
TEMPLATE_LIST = [
    ('huawei_vrp','bgp','peering'),('cisco_iosxe','bgp','peering'),('h3c_comware','bgp','peering'),
    ('juniper_junos','bgp','peering'),('arista_eos','bgp','peering'),
    ('huawei_vrp','bgp','route_reflector'),('cisco_iosxe','bgp','route_reflector'),('h3c_comware','bgp','route_reflector'),
    ('juniper_junos','bgp','route_reflector'),('arista_eos','bgp','route_reflector'),
    ('huawei_vrp','bgp','ipv6_family'),('cisco_iosxe','bgp','ipv6_family'),('h3c_comware','bgp','ipv6_family'),
    ('juniper_junos','bgp','ipv6_family'),('arista_eos','bgp','ipv6_family'),
    ('huawei_vrp','ospf','area_config'),('cisco_iosxe','ospf','area_config'),('h3c_comware','ospf','area_config'),
    ('juniper_junos','ospf','area_config'),('arista_eos','ospf','area_config'),
    ('huawei_vrp','ospf','interface'),('cisco_iosxe','ospf','interface'),('h3c_comware','ospf','interface'),
    ('juniper_junos','ospf','interface'),('arista_eos','ospf','interface'),
    ('huawei_vrp','ospf','stub_area'),('cisco_iosxe','ospf','stub_area'),('h3c_comware','ospf','stub_area'),
    ('juniper_junos','ospf','stub_area'),('arista_eos','ospf','stub_area'),
    ('huawei_vrp','vxlan','evpn_l2vpn'),('cisco_iosxe','vxlan','evpn_l2vpn'),('h3c_comware','vxlan','evpn_l2vpn'),
    ('juniper_junos','vxlan','evpn_l2vpn'),('arista_eos','vxlan','evpn_l2vpn'),
    ('huawei_vrp','vxlan','anycast_gateway'),('cisco_iosxe','vxlan','anycast_gateway'),('h3c_comware','vxlan','anycast_gateway'),
    ('juniper_junos','vxlan','anycast_gateway'),('arista_eos','vxlan','anycast_gateway'),
    ('huawei_vrp','vpn','ipsec_site2site'),('cisco_iosxe','vpn','ipsec_site2site'),('h3c_comware','vpn','ipsec_site2site'),
    ('juniper_junos','vpn','ipsec_site2site'),('arista_eos','vpn','ipsec_site2site'),
    ('huawei_vrp','vpn','ssl_remote'),('cisco_iosxe','vpn','ssl_remote'),('h3c_comware','vpn','ssl_remote'),
    ('juniper_junos','vpn','ssl_remote'),('arista_eos','vpn','ssl_remote'),
    ('huawei_vrp','interface','trunk'),('cisco_iosxe','interface','trunk'),('h3c_comware','interface','trunk'),
    ('juniper_junos','interface','trunk'),('arista_eos','interface','trunk'),
    ('huawei_vrp','interface','vlan'),('cisco_iosxe','interface','vlan'),('h3c_comware','interface','vlan'),
    ('juniper_junos','interface','vlan'),('arista_eos','interface','vlan'),
    ('huawei_vrp','static_route','default'),('cisco_iosxe','static_route','default'),('h3c_comware','static_route','default'),
    ('juniper_junos','static_route','default'),('arista_eos','static_route','default'),
    ('huawei_vrp','static_route','policy_route'),('cisco_iosxe','static_route','policy_route'),('h3c_comware','static_route','policy_route'),
    ('juniper_junos','static_route','policy_route'),('arista_eos','static_route','policy_route'),
    ('huawei_vrp','wireless','ssid'),('cisco_iosxe','wireless','ssid'),('h3c_comware','wireless','ssid'),
    ('juniper_junos','wireless','ssid'),('arista_eos','wireless','ssid'),
    ('huawei_vrp','wireless','roaming'),('cisco_iosxe','wireless','roaming'),('h3c_comware','wireless','roaming'),
    ('juniper_junos','wireless','roaming'),('arista_eos','wireless','roaming'),
]

QUESTION_HINTS = {
    ('bgp','peering'): 'eBGP peer 建立，与对端 AS 65001 互联',
    ('bgp','route_reflector'): 'iBGP Route Reflector 配置，本地 AS 65000 + 集群 ID 10.0.0.1',
    ('bgp','ipv6_family'): 'BGP IPv4+IPv6 双栈配置，对端 v4 peer 10.1.1.1 + v6 peer 2001:db8::2',
    ('ospf','area_config'): 'OSPF area 0 配置 + 网段通告',
    ('ospf','interface'): 'OSPF 接口配置 + 网络类型 broadcast',
    ('ospf','stub_area'): 'OSPF stub area 0.0.0.1 完全末梢（no-summary）',
    ('vxlan','evpn_l2vpn'): 'VXLAN EVPN L2VNI 10010 + BGP EVPN peer',
    ('vxlan','anycast_gateway'): 'VXLAN anycast-gateway VNI 10020，统一网关 MAC',
    ('vpn','ipsec_site2site'): 'IPsec site-to-site 隧道与对端 198.51.100.1（AES256+SHA256+PSK）',
    ('vpn','ssl_remote'): 'SSL VPN 远程接入配置（pool + 用户）',
    ('interface','trunk'): 'Trunk 端口 VLAN 10 配置',
    ('interface','vlan'): 'Vlanif 10 配置 + IP',
    ('static_route','default'): '默认路由 0.0.0.0/0 → 198.51.100.254',
    ('static_route','policy_route'): '策略路由：源 10.1.0.0/16 → 10.0.0.1',
    ('wireless','ssid'): 'WLAN SSID corp + wpa2-psk 配置',
    ('wireless','roaming'): 'WLAN 漫游组 mg1 + 多个 AP',
}

counter = {'written':0, 'skip':0}
nxt = find_next_id()
for vendor, protocol, feature in TEMPLATE_LIST:
    nxt += 0 if counter['written']==0 and counter['skip']==0 else 0
    hint = QUESTION_HINTS.get((protocol, feature), f'{protocol}/{feature} 配置')
    q = build_config_q(vendor, protocol, feature, nxt, hint)
    if q is None:
        counter['skip'] += 1
        continue
    p = f'{OUT}/{q["id"]}.yaml'
    yaml.dump(q, open(p,'w',encoding='utf-8'),
              default_flow_style=False, allow_unicode=True, sort_keys=False, width=240)
    counter['written'] += 1
    nxt += 1
    if counter['written']%20==0:
        print(f'  batch progress: {counter["written"]} written, {counter["skip"]} skip')

print(f'\n total written: {counter["written"]}')
print(f' total skip (Mist api or render fail): {counter["skip"]}')
