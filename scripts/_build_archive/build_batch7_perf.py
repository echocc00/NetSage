"""batch7 perf - 40 道 RDMA/RoCE/PFC 调优题"""
import yaml, os
OUT = 'F:/claudepc/NetSage/eval/dataset'

def save(q):
    p = f'{OUT}/{q["id"]}.yaml'
    yaml.dump(q, open(p,'w',encoding='utf-8'),
              default_flow_style=False, allow_unicode=True, sort_keys=False, width=240)

def P(id_off, title, vendor, version, difficulty, tags, requirement, bottleneck, tuning, verify):
    save({
        'id': f'NSG-Q-{id_off:04d}', 'title': title, 'category': 'perf', 'vendor': vendor,
        'version': version, 'difficulty': difficulty, 'tags': tags,
        'input': {
            'symptom': requirement,
            'device_info': {'model':'', 'version': version, 'interfaces': []},
            'question': '给出瓶颈定位 + 调优参数',
        },
        'expected_output': {
            'bottleneck': bottleneck,
            'tuning_params': tuning,
            'verify': verify,
            'references': [{'type':'vendor_doc','url':f'https://{vendor}.com/{tags[0]}','version':version,'title':f'{tags[0]} 调优章节'}],
        },
        'anti_examples': ['关闭 PFC', '建议重启设备', '无证据瞎猜'],
        'grading_rubric': {
            'must_have': ['PFC 优先级', 'ECN 阈值', 'buffer 配置'],
            'nice_to_have': ['DCQCN 调参', 'PFC watchdog', 'verify 命令'],
            'penalty': ['建议关闭 PFC'],
        },
    })

next_id = 373

# 1) RoCEv2 PFC 调优 × 10
PFC_TUNINGS = [
    ('AI 训练集群 RoCEv2 丢包，GPU 间 allreduce 延迟从 5μs 升到 50μs', 'PFC watchdog 未启用 + ECN 缺失'),
    ('RoCEv2 长 fat 流（incast），PFC 反复暂停雍塞', 'headroom buffer 不够'),
    ('多租户 RoCE，noisy neighbor 影响', 'PFC 优先级分配不全'),
    ('RoCEv2 with TCP 同时，TCP 抢占 RoCE 带宽', 'qos scheduler 缺乏对 RoCE 优先级保护'),
    ('RoCEv2 偶发丢包（incast）', 'PFC watchdog 设太短'),
    ('RoCE v2 与传统以太网并存', 'TC 调度未配置 RoCE priority'),
    ('RDMA NFS 客户端 reroute 频繁', 'PFC pause 触发盲区'),
    ('GPU Direct 性能差', 'GPU 端口 ECMP 路径不等分'),
    ('RoCEv2 PFC pause-frames 抖动', '设备低 buffer 边界'),
    ('存储 iWARP 与 RoCE 共存', '两类 RDMA 优先级抢占'),
]
for i, (req, bn) in enumerate(PFC_TUNINGS):
    P(next_id, f'RoCEv2 PFC 调优 {i+1}/10: {req[:30]}', 'huawei', 'VRP-8.180', 5, ['roce','pfc','ecn','dcb'],
      req, bn,
      {'pfc_priority': 3, 'pfc_headroom': '10KB', 'ecn_threshold': '150KB', 'ecn_ce_threshold': '200KB',
       'buffer_egress': 'shared', 'mtu': 9100},
      ['display dcb pfc', 'display roce ecn', 'display roce buffer'])
    next_id += 1

# 2) ECN/DCQCN 调优 × 8
ECN_TUNINGS = [
    ('RoCE ECN 阈值过低，触发频繁', 'ECN Kmin/Kmax 设错'),
    ('ECN 阈值过高无作用', 'ECN marking bypass'),
    ('DCQCN 算法失效', 'alpha/g 更新参数错'),
    ('ECN 队列 threshold 与 RoCE 不匹配', 'TC map 配置错'),
    ('ECN mark 频率过高', 'ECN queue threshold 调整'),
    ('AQM 算法切换', 'QoS 配置'),
    ('RDMA 拥塞窗口不一致', 'cwnd init 错'),
    ('ECN 没用导致 PFC pause 风暴', '综合调优'),
]
for i, (req, bn) in enumerate(ECN_TUNINGS):
    P(next_id, f'ECN 调优 {i+1}/8: {req[:30]}', 'cisco', 'IOS-XE-17.09', 5, ['ecn','dcqcn','qos'],
      req, bn,
      {'ecn_threshold_min': '150KB', 'ecn_threshold_max': '200KB', 'dcqcn_alpha': 0.3, 'dcqcn_g_init': 1024},
      ['show qos interface ecn', 'show dcb priority-flow-control'])
    next_id += 1

# 3) buffer/队列调优 × 6
BUFFER_TUNINGS = [
    ('25G RoCE 接口共享 buffer 低', 'headroom 不够'),
    ('PFC headroom 拥塞时 queue drop', 'headroom 太小'),
    ('设备 buffer 模式 dynamic vs static', '配置模式选错'),
    ('多队列 ECMP 负载不均', 'qos buffer share 不均衡'),
    ('RoCE 输出 drop 高', 'egress buffer overflow'),
    ('DCQCN pacing 慢', 'CPU 拥塞影响 PFC'),
]
for i, (req, bn) in enumerate(BUFFER_TUNINGS):
    P(next_id, f'Buffer 调优 {i+1}/6: {req[:30]}', 'huawei', 'VRP-8.180', 5, ['buffer','headroom','qos'],
      req, bn,
      {'headroom': '10KB', 'shared_dynamic': True, 'pause_threshold': 'auto'},
      ['display queue', 'display buffer'])
    next_id += 1

# 4) MTU/分片问题 × 4
MTU_TUNINGS = [
    ('RoCE 大包分片，CPU 高', 'MTU 小'),
    ('MTU 9216 不通', 'jumbo frame 未全局开'),
    ('MTU 跨设备不一致', 'MTU 配置错'),
    ('IPv6 分片丢', 'PMTUd 未启用'),
]
for i, (req, bn) in enumerate(MTU_TUNINGS):
    P(next_id, f'MTU 调优 {i+1}/4: {req[:30]}', 'cisco', 'IOS-XE-17.09', 4, ['mtu','jumbo','fragment'],
      req, bn,
      {'mtu': 9216, 'jumbo_frame': True, 'pmtud': True},
      ['show interface mtu'])
    next_id += 1

# 5) IB 子网 × 6
IB_TUNINGS = [
    ('InfiniBand LID 冲突', 'subnet manager 双启'),
    ('IB 路径 MTU 不通', 'IB subnet max MTU 设置错'),
    ('IB VL/VL15 分配错', 'IB 队列权重设置错'),
    ('IB 分区 (partition) 设置', 'IB PKey 错配'),
    ('IB subnet manager 切换频繁', 'IB SM master/standby 错'),
    ('IB 自适应路由 vs 边沿路由', 'IB 路由模式选择'),
]
for i, (req, bn) in enumerate(IB_TUNINGS):
    P(next_id, f'InfiniBand 调优 {i+1}/6: {req[:30]}', 'mellanox', 'MLNX-OS 4.x', 5, ['infiband','lid','vl','partition'],
      req, bn,
      {'lid_start': 1, 'sm_priority': 5, 'vl15': 'management', 'pkey': '0x7FFF'},
      ['show topology', 'show vpath'])
    next_id += 1

# 6) GPU Direct / RDMA 性能 × 6
GPU_TUNINGS = [
    ('GPU Direct P2P 慢', 'P2P 设错'),
    ('RDMA Write 单边延迟高', 'inline data 没启用'),
    ('GPU-Direct RDMA 调试', 'pin memory 缺失'),
    ('Multi-GPU NCCL 慢', 'IB plugin 缺失'),
    ('GPU Direct 内存一致性问题', 'GPU 驱动版本'),
    ('DPDK 链路 RSS 不均', 'numa 节点错配'),
]
for i, (req, bn) in enumerate(GPU_TUNINGS):
    P(next_id, f'GPU Direct 调优 {i+1}/6: {req[:30]}', 'cisco', 'IOS-XE-17.09', 5, ['gpu-direct','rdma','dpdk','nccl'],
      req, bn,
      {'nccl_ib_disable': False, 'nccl_p2p_level': 'sys', 'cuda_cache_config': 'cudaFuncCachePreferL1'},
      ['show rdma', 'show gpu-direct'])
    next_id += 1

print(f'batch7 perf done')

from collections import Counter
cats = Counter()
for f in os.listdir(OUT):
    if not f.endswith('.yaml'): continue
    d = yaml.safe_load(open(f'{OUT}/{f}'))
    cats[d.get('category','unknown')] += 1
print(f'Total={sum(cats.values())} {dict(cats)}')
