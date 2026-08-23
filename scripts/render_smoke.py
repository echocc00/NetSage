"""模板渲染烟测脚本 - 检查 10 个新增 VXLAN 模板是否都能渲染出 CLI。
文件路径：scripts/render_smoke.py
调用：python scripts/render_smoke.py
"""
import os, sys
from jinja2 import Environment, FileSystemLoader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env = Environment(loader=FileSystemLoader(ROOT))

SAMPLES = {
  'huawei_vrp/vxlan/evpn_l2vpn.j2': {
    'local_asn': 65000, 'rd_ip': '10.0.0.1',
    'vtep_peers':[{'address':'10.1.1.1','remote_asn':65001}],
    'bridge_domain_id':10,'vni':10010,'vbdif_ip':'10.1.10.1/24','advertise_arp':True},
  'huawei_vrp/vxlan/anycast_gateway.j2': {
    'bridge_domain_id':20,'vni':10020,'vbdif_ip':'10.1.20.1/24',
    'anycast_gw_mac':'00-00-5e-00-01-20'},
  'cisco_iosxe/vxlan/evpn_l2vpn.j2': {
    'local_asn':65000,'router_id':'10.0.0.1',
    'vtep_peers':[{'address':'10.1.1.1','remote_asn':65001}],
    'vlan_id':10,'vni':10010,'evpn_instance_id':10,
    'rd':'10.0.0.1:10','route_target':'65000:10010'},
  'cisco_iosxe/vxlan/anycast_gateway.j2': {
    'anycast_gw_mac':'0000.5e00.0120','vlan_id':20,'vni':10020,
    'vlanif_ip':'10.1.20.1/24','evpn_instance_id':20,
    'rd':'10.0.0.1:20','route_target':'65000:10020','local_asn':65000},
  'h3c_comware/vxlan/evpn_l2vpn.j2': {
    'local_asn':65000,
    'vtep_peers':[{'address':'10.1.1.1','remote_asn':65001}],
    'vsi_name':'vsi10','vni':10010,'vsi_interface_id':1,'vsi_interface_ip':'10.1.10.1/24'},
  'h3c_comware/vxlan/anycast_gateway.j2': {
    'anycast_gw_mac':'0000-5e00-0120','vsi_name':'vsi20','vni':10020,
    'vsi_interface_id':2,'vsi_interface_ip':'10.1.20.1/24'},
  'juniper_junos/vxlan/evpn_l2vpn.j2': {
    'instance_name':'vsrx-evpn','vlan_id':10,'vni':10010,'rd':'10.0.0.1:10',
    'vrf_target':'65000:10010','bgp_neighbor':'10.1.1.1','local_address':'10.0.0.1'},
  'juniper_junos/vxlan/anycast_gateway.j2': {
    'instance_name':'anycast-gw','vlan_id':20,'vni':10020,'irb_unit':20,
    'irb_ip':'10.1.20.1/24','anycast_gw_mac':'00:00:5e:00:01:20'},
  'arista_eos/vxlan/evpn_l2vpn.j2': {
    'local_asn':65000,'router_id':'10.0.0.1',
    'vtep_peers':[{'address':'10.1.1.1','remote_asn':65001}],
    'vlan_id':10,'vni':10010,'vxlan_interface':'Vxlan1'},
  'arista_eos/vxlan/anycast_gateway.j2': {
    'anycast_gw_mac':'00:00:5e:00:01:20','vlan_id':20,'vni':10020,
    'vlanif_ip':'10.1.20.1/24','vxlan_interface':'Vxlan1','local_asn':65000,
    'vtep_peers':[{'address':'10.1.1.1','remote_asn':65001}]},
}

ok = 0; fails = []
for path, ctx in SAMPLES.items():
    full = 'backend/templates/' + path
    try:
        tpl = env.get_template(full)
        out = tpl.render(**ctx).rstrip()
        print(f'== {path} == ({len(out)} bytes)')
        if ok < 3:
            print(out[:300])
            print('---')
        ok += 1
    except Exception as e:
        fails.append((path, str(e)[:300]))
        print(f'FAIL {path}: {e}')

print(f'\nRender OK: {ok}/{len(SAMPLES)}')
if fails:
    print('FAIL details:')
    for f in fails: print(f)
sys.exit(0 if ok == len(SAMPLES) else 1)
