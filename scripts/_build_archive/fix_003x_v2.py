"""最稳的方式：用 yaml.safe_load 把正确的字段读出来（参考之前的 lift_rubric.py 思路），
然后用 yaml.dump 重写。但当前文件 yaml.safe_load 已经丢失 anti_examples / grading_rubric 字段。
所以这个文件需要手工提取这两个字段（直接从原始字符串切片），再 dump。"""
import re, yaml

FILES = ['NSG-Q-0031.yaml', 'NSG-Q-0032.yaml', 'NSG-Q-0033.yaml']

def extract_block(text, key):
    """从 YAML 文本中提取顶级 key 对应的 block 字符串（多行）。"""
    pattern = re.compile(rf'^{re.escape(key)}:\s*$', re.M)
    m = pattern.search(text)
    if not m:
        return None
    start = m.start()
    # 找后续第一个不缩进或更浅缩进的行
    pos = m.end()
    lines = text[pos:].split('\n')
    block = []
    for line in lines[1:]:
        # 如果空行，跳过
        if not line.strip():
            block.append(line)
            continue
        # 如果首字符不是空格（顶级），结束
        if not line.startswith(' ') and not line.startswith('\t'):
            break
        block.append(line)
    return '\n'.join(block).rstrip('\n')

def fix(path):
    txt = open(path, encoding='utf-8').read()
    # 提取 anti_examples 和 grading_rubric
    ae = extract_block(txt, 'anti_examples')
    gr = extract_block(txt, 'grading_rubric')
    if not ae or not gr:
        print(f'{path}: missing one of ae/gr, skip')
        return
    # 把文件中这两个块（连同前置 -2 空格缩进）删掉
    # 简单做法：删除其全部行
    lines = txt.split('\n')
    new = []
    skip_block = None
    skip_depth = 0
    depth_at_start = 2  # 我之前全是 2 空格缩进
    for line in lines:
        # 检测开始
        if skip_block is None:
            if line.strip() in ('  anti_examples:', '  grading_rubric:'):
                skip_block = line.strip().rstrip(':')
                skip_depth = 2
                continue
        else:
            # 已读到 mid of block：检测是否结束（无缩进行）
            if line.strip() == '':
                new.append(line)
                continue
            indent = len(line) - len(line.lstrip())
            if indent <= 2:
                # block 结束
                skip_block = None
                # 当前行也要保留（可能是下一个 top key）
                if line.strip() in ('  anti_examples:', '  grading_rubric:'):
                    skip_block = line.strip().rstrip(':')
                    continue
                new.append(line)
                continue
            else:
                # 还在 block 内
                continue
        new.append(line)
    fixed = '\n'.join(new)
    # 现在文件是合法 YAML 但仍不带 anti_examples / grading_rubric
    # 用 yaml.safe_load 读，再附加两个字段，dump
    d = yaml.safe_load(fixed)
    # 重写 yaml 内嵌字段（保持 block 风格）
    d['anti_examples'] = yaml.safe_load(ae) if ae else []
    d['grading_rubric'] = yaml.safe_load(gr) if gr else {}
    # 按顺序 dump（sort_keys=False 保留顺序）
    order = ['id','title','category','vendor','version','difficulty','tags',
             'input','expected_output','anti_examples','grading_rubric']
    d2 = {k:d[k] for k in order if k in d}
    for k in d:
        if k not in d2:
            d2[k] = d[k]
    yaml.dump(d2, open(path,'w',encoding='utf-8'),
              default_flow_style=False, allow_unicode=True, sort_keys=False)
    # 验证
    d_after = yaml.safe_load(open(path))
    print(f'{path}: keys={sorted(d_after.keys())}, ae={len(d_after.get("anti_examples",[]))}, gr_keys={sorted((d_after.get("grading_rubric") or {}).keys())}')

for f in FILES:
    fix(f'eval/dataset/{f}')
