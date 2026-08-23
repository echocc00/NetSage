"""bulk-fix YAML 误改问题：
1. 把 `  - "A", "B", "C", "D"` 这种行内逗号分隔的，多元素同行，拆成多行
2. 把 `key: ["A", "B"]` 单元素行并 → 已修复（无）
"""
import os, re, yaml

QFILES = sorted([f for f in os.listdir('eval/dataset') if f.endswith('.yaml')])

def expand_inline_arrays(line):
    """检测行是否形如 `  - "X", "Y", "Z"` 若是，展开成多行。返回 list[str] 或 None。"""
    m = re.match(r'^(\s*)- ("[^"]*")(\s*,\s*"[^"]*")+$', line)
    if not m:
        return None
    indent = re.match(r'^(\s*)', line).group(1)
    parts = re.findall(r'"[^"]*"', line)
    return [f"{indent}- {p}" for p in parts]

err=[]
for q in QFILES:
    p = 'eval/dataset/' + q
    text = open(p, encoding='utf-8').read()
    out=[]
    changed = False
    for line in text.splitlines():
        if expanded := expand_inline_arrays(line):
            out.extend(expanded)
            changed = True
        else:
            out.append(line)
    if changed:
        open(p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')

# 校验
err=[]
for q in QFILES:
    p='eval/dataset/'+q
    try:
        d=yaml.safe_load(open(p))
        if not isinstance(d,dict): err.append((p,'not-dict')); continue
        must=['id','title','category','vendor','version','difficulty','tags','input','expected_output','anti_examples','grading_rubric']
        miss=[m for m in must if m not in d]
        if miss: err.append((p,'miss:'+str(miss))); continue
        rc=d['expected_output'].get('root_causes',[])
        if not isinstance(rc,list) or len(rc) < 1:
            err.append((p,f'root_causes<1:{len(rc) if isinstance(rc,list) else "na"}'))
        # 注意老的 2-4 是 stub，可能 root_causes 为空，不强制
    except Exception as e:
        err.append((p,f'PARSE:{str(e)[:160]}'))
print('err:',err if err else 'NONE')
print('total:',len(QFILES))
