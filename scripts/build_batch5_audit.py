"""batch5 audit 题 - 79 道，基于 30 + 基线规则自动反向构造违规配置
每题：场景化描述 + 违规配置 + severity + remediation
"""
import yaml, os

OUT = 'F:/claudepc/NetSage/eval/dataset'

def save(q):
    p = f'{OUT}/{q["id"]}.yaml'
    yaml.dump(q, open(p,'w',encoding='utf-8'),
              default_flow_style=False, allow_unicode=True, sort_keys=False, width=240)

def A(id_off, title, vendor, version, difficulty, tags, baseline_id, config, findings):
    save({
        'id': f'NSG-Q-{id_off:04d}', 'title': title, 'category': 'audit', 'vendor': vendor,
        'version': version, 'difficulty': difficulty, 'tags': tags,
        'input': {
            'symptom': '审计以下配置的安全合规性',
            'device_info': {'model': '', 'version': version, 'interfaces': []},
            'question': f'列出风险点 + 加固建议 + 合规分（基线 {baseline_id}）',
            'config_snippet': config,
        },
        'expected_output': {'findings': findings, 'score': findings_score(findings),
                            'references': [{'type': 'standard', 'url': f'https://cis-security/{baseline_id}',
                                           'version': version, 'title': f'CIS {baseline_id} 章节'}]},
        'anti_examples': ['请重启设备', '推荐清除配置', '遗漏 critical 项'],
        'grading_rubric': {
            'must_have': [f'识别 {baseline_id} 主要风险', '给整改建议', 'severity 分级'],
            'nice_to_have': ['引用基线规则 ID', '给合规分'],
            'penalty': ['推荐重启设备', '遗漏 critical 项'],
        },
    })

def findings_score(fs):
    # 简单启发：critical-30 / high-15 / medium-5
    s = 100
    for f in fs:
        v = f.get('severity','medium')
        if v == 'critical': s -= 30
        elif v == 'high': s -= 15
        elif v == 'medium': s -= 5
        elif v == 'low': s -= 2
    return max(0, min(100, s))

# 79 道 audit - 按 7 类基线规则构造
CATEGORIES = [
    # (cat_name, count)
    ('auth', 20),    # CIS-AUTH-01~05 × 4 厂商
    ('mgmt', 16),    # CIS-MGMT-01~04 × 4
    ('proto', 12),   # CIS-PROTO × 3 × 4
    ('acl', 12),     # CIS-ACL × 3 × 4
    ('acl_analysis', 10),  # Batfish ACL
    ('attack', 9),   # 综合
]

specs = [
    # 1) auth × 20
    ('telnet-disable', 'huawei', 'VRP-8.180', 'a] telnet server enable', 'auth-01'),
    ('ssh-enable', 'huawei', 'VRP-8.180', 'a] protocol inbound ssh\nb] telnet server enable', 'auth-02'),
    ('plaintext-password', 'huawei', 'VRP-8.180', 'a] local-user u1 password simple 123456', 'auth-03'),
    ('default-account', 'huawei', 'VRP-8.180', 'a] local-user admin password cipher xxx', 'auth-04'),
    ('aaa-auth-bypass', 'huawei', 'VRP-8.180', 'a] user-interface vty 0 4\n protocol inbound none', 'auth-05'),
    ('telnet-disable', 'cisco', 'IOS-XE-17.09', 'line vty 0 4\n transport input telnet ssh', 'auth-01'),
    ('ssh-only', 'cisco', 'IOS-XE-17.09', 'line vty 0 4\n transport input ssh', 'auth-02'),
    ('enable-password-plain', 'cisco', 'IOS-XE-17.09', 'enable password cisco123', 'auth-03'),
    ('default-admin', 'cisco', 'IOS-XE-17.09', 'username admin privilege 15 password 0 admin123', 'auth-04'),
    ('auth-allow-guest', 'cisco', 'IOS-XE-17.09', 'aaa authentication login default group tacacs+ local\n no aaa new-model', 'auth-05'),
    ('telnet-disable', 'h3c', 'Comware-7.1.070', 'telnet server enable', 'auth-01'),
    ('ssh-only', 'h3c', 'Comware-7.1.070', 'public-key local create rsa', 'auth-02'),
    ('plaintext-password', 'h3c', 'Comware-7.1.070', 'local-user u1 password simple ABC', 'auth-03'),
    ('super-password', 'h3c', 'Comware-7.1.070', 'super password level 3 cipher ABC', 'auth-04'),
    ('auth-allow', 'h3c', 'Comware-7.1.070', 'user-interface vty 0 4\n authentication-mode none', 'auth-05'),
    ('telnet-disable', 'juniper', '21.2R1', 'set system services telnet', 'auth-01'),
    ('ssh-only', 'juniper', '21.2R1', 'set system services ssh', 'auth-02'),
    ('plaintext-password', 'juniper', '21.2R1', 'set system login user u1 authentication plain-text-password ABC', 'auth-03'),
    ('super-password', 'juniper', '21.2R1', 'set system login user u1 class super-user', 'auth-04'),
    ('auth-bypass', 'juniper', '21.2R1', 'set system services telnet connection-limit 50 rate-limit 20', 'auth-05'),
    # 2) mgmt × 16
    ('snmp-v2c', 'huawei', 'VRP-8.180', 'snmp-agent community read public\n snmp-agent protocol source-interface Vlan100', 'mgmt-01'),
    ('ntp-no-auth', 'huawei', 'VRP-8.180', 'ntp-service unicast-server 10.1.1.100', 'mgmt-02'),
    ('log-no-encrypt', 'huawei', 'VRP-8.180', 'info-center enable\n info-center loghost 10.1.1.200', 'mgmt-03'),
    ('http-server', 'huawei', 'VRP-8.180', 'http server enable\n http server port 80', 'mgmt-04'),
    ('snmp-v2c', 'cisco', 'IOS-XE-17.09', 'snmp-server community public RO', 'mgmt-01'),
    ('ntp-no-auth', 'cisco', 'IOS-XE-17.09', 'ntp server 10.1.1.100', 'mgmt-02'),
    ('log-no-encrypt', 'cisco', 'IOS-XE-17.09', 'logging host 10.1.1.200', 'mgmt-03'),
    ('http-server', 'cisco', 'IOS-XE-17.09', 'ip http server\n ip http secure-server', 'mgmt-04'),
    ('snmp-v2c', 'h3c', 'Comware-7.1.070', 'snmp-agent community write public', 'mgmt-01'),
    ('ntp-no-auth', 'h3c', 'Comware-7.1.070', 'ntp-service unicast-server 10.1.1.100', 'mgmt-02'),
    ('log-no-encrypt', 'h3c', 'Comware-7.1.070', 'info-center enable\n info-center loghost 10.1.1.200', 'mgmt-03'),
    ('http-server', 'h3c', 'Comware-7.1.070', 'ip http enable', 'mgmt-04'),
    ('snmp-v2c', 'juniper', '21.2R1', 'set snmp community public authorization read-only', 'mgmt-01'),
    ('ntp-no-auth', 'juniper', '21.2R1', 'set system ntp server 10.1.1.100', 'mgmt-02'),
    ('log-no-encrypt', 'juniper', '21.2R1', 'set system syslog host 10.1.1.200', 'mgmt-03'),
    ('http-server', 'juniper', '21.2R1', 'set system services web-management http', 'mgmt-04'),
    # 3) proto × 12
    ('bgp-no-md5', 'huawei', 'VRP-8.180', 'bgp 65001\n peer 10.1.1.2 as-number 65002', 'proto-01'),
    ('ospf-no-auth', 'huawei', 'VRP-8.180', 'ospf 1\n area 0.0.0.0\n  network 10.1.1.0 0.0.0.255', 'proto-02'),
    ('rip-no-auth', 'huawei', 'VRP-8.180', 'rip 1\n network 10.0.0.0', 'proto-03'),
    ('bgp-md5', 'cisco', 'IOS-XE-17.09', 'router bgp 65001\n neighbor 10.1.1.2 remote-as 65002', 'proto-01'),
    ('ospf-no-auth', 'cisco', 'IOS-XE-17.09', 'router ospf 1\n network 10.1.1.0 0.0.0.255 area 0', 'proto-02'),
    ('eigrp-no-auth', 'cisco', 'IOS-XE-17.09', 'router eigrp 1\n network 10.1.1.0 0.0.0.255', 'proto-03'),
    ('bgp-no-md5', 'h3c', 'Comware-7.1.070', 'bgp 65001\n peer 10.1.1.2 as-number 65002', 'proto-01'),
    ('ospf-no-auth', 'h3c', 'Comware-7.1.070', 'ospf 1\n area 0.0.0.0\n  network 10.1.1.0 0.0.0.255', 'proto-02'),
    ('isis-no-auth', 'h3c', 'Comware-7.1.070', 'isis 1\n network-entity 49.0001.0000.0000.0001.00', 'proto-03'),
    ('bgp-no-md5', 'juniper', '21.2R1', 'set protocols bgp group EBGP neighbor 10.1.1.2 peer-as 65002', 'proto-01'),
    ('ospf-no-auth', 'juniper', '21.2R1', 'set protocols ospf area 0.0.0.0 interface ge-0/0/0', 'proto-02'),
    ('rip-no-auth', 'juniper', '21.2R1', 'set protocols rip group G1 neighbor fe80::1', 'proto-03'),
    # 4) acl × 12
    ('permit-any-any', 'huawei', 'VRP-8.180', 'acl 3000\n rule 5 permit ip', 'acl-01'),
    ('unset-anti-spoof', 'huawei', 'VRP-8.180', 'interface 10GE1/0/1\n ip address 10.1.1.1 24', 'acl-02'),
    ('unused-allow-any', 'huawei', 'VRP-8.180', 'acl 3001\n rule 10 permit tcp any any eq 22\n # 但未应用', 'acl-03'),
    ('permit-any', 'cisco', 'IOS-XE-17.09', 'access-list 100 permit ip any any', 'acl-01'),
    ('unset-anti-spoof', 'cisco', 'IOS-XE-17.09', 'interface g1/0/1\n ip address 10.1.1.1 255.255.255.0', 'acl-02'),
    ('unused-allow', 'cisco', 'IOS-XE-17.09', 'ip access-list extended ACL-1\n permit tcp any any eq 22', 'acl-03'),
    ('permit-any', 'h3c', 'Comware-7.1.070', 'acl number 3000\n rule 5 permit ip', 'acl-01'),
    ('unset-anti-spoof', 'h3c', 'Comware-7.1.070', 'interface 10GE1/0/1\n ip address 10.1.1.1 255.255.255.0', 'acl-02'),
    ('unused-allow', 'h3c', 'Comware-7.1.070', 'acl number 3001\n rule 10 permit tcp any any eq 22', 'acl-03'),
    ('permit-any', 'juniper', '21.2R1', 'set firewall family inet filter F1 term 1 then accept', 'acl-01'),
    ('unset-anti-spoof', 'juniper', '21.2R1', 'set interfaces ge-0/0/0 unit 0 family inet address 10.1.1.1/24', 'acl-02'),
    ('unused-allow', 'juniper', '21.2R1', 'set firewall family inet filter F1 term 1 from protocol tcp\n set firewall family inet filter F1 term 1 then accept', 'acl-03'),
    # 5) acl_analysis × 10 (shadowed / unused / redundant)
    ('shadowed', 'huawei', 'VRP-8.180', 'acl 3000\n rule 5 deny ip any any\n rule 10 permit ip 10.1.0.0 0.0.255.255 any', 'acl-04'),
    ('overlap', 'huawei', 'VRP-8.180', 'acl 3001\n rule 5 permit tcp any any eq 80\n rule 10 permit tcp any host 10.1.1.2 eq 80', 'acl-05'),
    ('shadowed', 'cisco', 'IOS-XE-17.09', 'ip access-list extended ACL-1\n deny ip any any\n permit ip 10.1.0.0 0.0.255.255 any', 'acl-04'),
    ('overlap', 'cisco', 'IOS-XE-17.09', 'ip access-list extended ACL-1\n permit tcp any any eq 80\n permit tcp any host 10.1.1.2 eq 80', 'acl-05'),
    ('shadowed', 'h3c', 'Comware-7.1.070', 'acl number 3000\n rule 5 deny ip any any\n rule 10 permit ip 10.1.0.0 0.0.255.255 any', 'acl-04'),
    ('overlap', 'h3c', 'Comware-7.1.070', 'acl number 3001\n rule 5 permit tcp any any eq 80\n rule 10 permit tcp any host 10.1.1.2 eq 80', 'acl-05'),
    ('shadowed', 'juniper', '21.2R1', 'set firewall family inet filter F1 term 1 then discard\n set firewall family inet filter F1 term 2 from source-address 10.1.0.0/16 then accept', 'acl-04'),
    ('overlap', 'juniper', '21.2R1', 'set firewall family inet filter F1 term 1 from protocol tcp\n set firewall family inet filter F1 term 1 then accept\n set firewall family inet filter F1 term 2 from source-address 10.1.1.2\n set firewall family inet filter F1 term 2 then accept', 'acl-05'),
    ('shadowed', 'arista', '4.24', 'ip access-list ACL-1\n deny ip any any\n permit ip 10.1.0.0 0.0.255.255 any', 'acl-04'),
    ('overlap', 'arista', '4.24', 'ip access-list ACL-2\n permit tcp any any eq 80\n permit tcp any host 10.1.1.2 eq 80', 'acl-05'),
    # 6) attack × 9
    ('default-snmp', 'huawei', 'VRP-8.180', 'snmp-agent community read public\n snmp-agent community write public', 'attack-01'),
    ('default-tenant-vrf', 'cisco', 'IOS-XE-17.09', 'vrf definition default\n no description', 'attack-02'),
    ('invalid-path', 'h3c', 'Comware-7.1.070', 'ip route-static 0.0.0.0 0.0.0.0 10.1.1.1 preference 1', 'attack-03'),
    ('route-injection', 'juniper', '21.2R1', 'set routing-options static route 0.0.0.0/0 next-hop 10.1.1.1', 'attack-04'),
    ('public-ssh', 'huawei', 'VRP-8.180', 'ssh server-source -i Vlan100\n ssh server-source all-interface', 'attack-05'),
    ('udf-allow', 'cisco', 'IOS-XE-17.09', 'service internal\n service unsupported-configuration', 'attack-06'),
    ('no-control-plane', 'h3c', 'Comware-7.1.070', '# 未配 control-plane protection', 'attack-07'),
    ('exposed-ssh-port', 'juniper', '21.2R1', 'set system services ssh port 22', 'attack-08'),
    ('plain-creds', 'arista', '4.24', 'tacacs-server host 10.1.1.99 key 0 NetSys@2024', 'attack-09'),
]

import yaml
next_id = 213
for rule_id, vendor, version, config, baseline in specs:
    # 按 baseline 推断 severity
    if rule_id in ('permit-any','shadowed','default-snmp','public-ssh','no-control-plane','exposed-ssh-port'):
        sev = 'critical'
    elif rule_id in ('plaintext-password','default-account','snmp-v2c','http-server','bgp-no-md5','log-no-encrypt','plain-creds'):
        sev = 'high'
    elif rule_id in ('super-password','enable-password-plain','unset-anti-spoof','overlap','default-tenant-vrf','route-injection','plain-creds','udf-allow'):
        sev = 'medium'
    else:
        sev = 'medium'
    title = f'审计 {vendor} {rule_id.upper().replace("-"," ")} ({baseline} 章节)'
    config_str = config.replace('\\n', '\n')
    findings = [
        {'rule_id': baseline.upper(), 'severity': sev,
         'description': f'配置违反 {baseline} 基线：{rule_id}',
         'remediation': f'对照 {baseline} 章节整改（清掉配置 + 启用合规配置）'},
    ]
    A(next_id, title, vendor, version, 3, [rule_id], baseline, config_str, findings)
    next_id += 1

from collections import Counter
cats = Counter()
for f in os.listdir(OUT):
    if not f.endswith('.yaml'): continue
    d = yaml.safe_load(open(f'{OUT}/{f}'))
    cats[d.get('category','unknown')] += 1
print(f'Total={sum(cats.values())} {dict(cats)}')
