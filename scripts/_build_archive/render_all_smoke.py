"""全量模板渲染烟测 - 自动发现所有 .j2，给最小可行默认参数验证。
调用：python scripts/render_all_smoke.py
退出码：0=全部通过；1=有失败。
"""
import os, sys, glob, json
from jinja2 import Environment, FileSystemLoader, UndefinedError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env = Environment(loader=FileSystemLoader(ROOT))

# 自动发现所有模板（glob 不支持 root_dir，老办法）
TEMPLATES = sorted(glob.glob(os.path.join(ROOT, 'backend/templates/**/*.j2'), recursive=True))
TEMPLATES = [os.path.relpath(p, ROOT).replace('\\','/') for p in TEMPLATES]

# 默认最小可行参数（按 template_id 前缀分配）
def params_for(path):
    fid = path.replace('/', '_').replace('.j2','')
    # 简单兜底：很多字段需要满足。Jinja2 中 is defined 的检查会容忍 missing。
    return {
        # 通用
        'local_asn': 65000, 'remote_asn': 65001, 'router_id': '10.0.0.1',
        'peers': [{'address':'10.1.1.1','remote_asn':65001}],
        'vtep_peers': [{'address':'10.1.1.1','remote_asn':65001}],
        'router-id': '10.0.0.1',
        'rd': '10.0.0.1:10','route_target': '65000:10010','vrf_target': '65000:10010',
        'rd_ip': '10.0.0.1','bgp_neighbor': '10.1.1.1','local_address': '10.0.0.1',
        # vxlan
        'bridge_domain_id': 10,'vni': 10010,'vbdif_ip': '10.1.10.1/24',
        'advertise_arp': True,'anycast_gw_mac': '00:00:5e:00:01:20',
        'vsi_name': 'vsi10','vsi_interface_id': 1,'vsi_interface_ip': '10.1.10.1/24',
        'vsi_interface_id': 1,'instance_name': 'evpn10','vlan_id': 10,'vlanif_ip': '10.1.10.1/24',
        'evpn_instance_id': 10,'irb_unit': 10,'irb_ip': '10.1.10.1/24','vxlan_interface': 'Vxlan1',
        # interface
        'interface_name': 'GigabitEthernet0/0/1','native_vlan': 10,
        'ip': '10.1.10.1','mask': '255.255.255.0','description': 'test',
        # static route
        'dest': '192.168.0.0','next_hop': '10.0.0.254','preference': 60,'remote_mask': '24',
        # ipsec
        'proposal_name': 'p1','encryption': 'aes-cbc-128',
        'authentication': 'pre-share','integrity': 'sha2-256','dh_group': 'group14','key_size': 128,
        'esp_auth': 'sha2-256','esp_encrypt': 'aes-cbc-128','encapsulation_mode': 'tunnel',
        'peer_name': 'peer1','pre_shared_key': 'key123','remote_ip': '10.1.2.1',
        'ipsec_proposal_name': 'p2','transform_set': 'ts1',
        'policy_name': 'pol1','sequence': 1,'acl_number': 3000,'netmask': '255.255.255.252',
        'remote_subnet': '192.168.10.0','remote_mask': '255.255.255.0','nat_group': 'ng1',
        'sa_strength': 'esp-aes-128-sha1','pfs_group': 14,'proposal_id': '1','local_spi': 'auto',
        'remote_spi': 'auto','sa_lifetime': 28800,'sa_lifetime_bytes': 'GB',
        # ssl
        'gateway_name': 'gw1','gateway_ip': '10.1.1.10','port': 443,
        'policy_id': '1','pool_name': 'p1','pool_start_ip': '10.1.10.1','pool_end_ip': '10.1.10.254',
        'pool_range_low': '10.1.10.1','pool_range_high': '10.1.10.254',
        'policy_group_name': 'pg1','url_list_name': 'ul1','intranet_url': 'http://intranet',
        'intranet_path': 'home','group_name': 'g1',
        'user_domain': 'default','password_hash': 'hash','user_name': 'u1','password': 'pw',
        'keepalive': 300,
        'client_name': 'c1','cert_id': 'cert1','address_name': 'addr1',
        'service_domain': 'any','trust_zone': 'trust','aaa_profile_name': 'aaa1',
        'rule_id': 1,'radius_server_name': 'r1','radius_ip': '10.1.1.99','radius_secret': 'sec',
        'cipher_list': 'AES256-SHA256','session_cache_timeout': 600,'ssl_profile': 'ssl1',
        'auth_policy_name': 'a1','acl_name': 'acl1',
        # bgp rr
        'cluster_id': '10.0.0.1','group_name': 'g1','clients':[{'address':'10.1.1.10','asn':65000}],
        'client_asn': 65000,
        # ospf interface
        'process_id': 1,'area_id': '0.0.0.0','network_type': 'broadcast','cost': 10,
        'authentication': True,'auth_type': 'md5','auth_key': 'k1',
        'ospf_area_md5_key_id': 1,
        # wireless
        'wmm_name': 'wmm1','radio_name': 'r1','channel': 36,'power': 50,
        'radio_type': 'ieee80211ax','radio_type_2g': '802.11ax','radio_type_5g': '802.11ax',
        'channel_2g': 6,'channel_5g': 36,'power_2g': 50,'power_5g': 50,
        'traffic_name': 't1','forwarding_mode': 'direct',
        'security_name': 'sec1','security_policy': 'wpa2-psk','ssid': 'corp',
        'psk_passphrase': 'pass1234','ap_group_name': 'ag1',
        'ap_id': 1,'ap_mac': 'aabb.ccdd.eeff','ap_name': 'ap01',
        'vap_name': 'v1','mobility_group': 'mg1','mobility_group_name': 'mg1',
        'domain_name': 'dom','channel_24': 6,'power_24': 50,
        'service_template': 'st1','wlan_id': 1,'profile_name': 'prof1',
        'policy_type': 'wpa2','session_timeout': 1800,'vlan_id': 10,
        'tag_policy_name': 'tp1','site_tag_name': 'ts1','ap_model': 'AP-9150',
        'cipher': 'aes-ccmp','security_ie': 'rsn','ap_serial': 'SN123',
        'roaming_mode': 'enable','reauth_timeout': 60,'roam_leverage': 5,
        'roam_threshold': -65,'sticky_threshold': -75,
        'idle_time': 5,'mobility_mac': 'aabb.ccdd.0001','rf_tag_name': 'rf1',
        'rf_profile_name': 'rf1','policy_name': 'p1','policy_tag_name': 'tp1',
        'akm': 'psk',
    }

ok = 0; fails = []
for path in TEMPLATES:
    full = path.replace('\\', '/')
    try:
        tpl = env.get_template(full)
        out = tpl.render(**params_for(full))
        if not out.strip():
            fails.append((full, 'empty output'))
            continue
        ok += 1
    except UndefinedError as e:
        # 一些模板需要的非通用字段缺失，但模板不该引用 undefined
        # 我们作为软失败处理：实际渲染时调用方负责提供
        fails.append((full, f'undefined: {str(e)[:120]}'))
    except Exception as e:
        fails.append((full, f'{type(e).__name__}: {str(e)[:160]}'))

print(f'Total templates: {len(TEMPLATES)} | OK: {ok} | FAIL: {len(fails)}')
for f, why in fails[:30]:
    print(f'  FAIL: {f}: {why}')
sys.exit(0 if ok == len(TEMPLATES) else 1)
