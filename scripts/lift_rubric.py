"""把 anti_examples 与 grading_rubric 提回到题目顶级（与 expected_output 平级）。
bug：之前误放进 expected_output 内（缩进 2 空格），应该为 0 空格。
检测：找到 anti_examples: 缩进 <4 空格的行，把 4+ 空格缩进替换为 0 空格。
"""
import os, re, yaml

def fix(path):
    txt = open(path, encoding='utf-8').read()
    lines = txt.split('\n')
    new=[]
    in_expected_output = False
    for line in lines:
        # 检测 expected_output: 后面跟着 anti_examples（line startswith 2-space anti_examples）
        if re.match(r'^  anti_examples:', line):
            new.append(re.sub(r'^  ', '', line, count=1))
            continue
        if re.match(r'^  grading_rubric:', line):
            # 整段块是缩进的，移 2 空格
            continue  # 先标记，开始剥
        # anti_examples 之后所有后续 sibling 0 缩进 / grading_rubric 兄弟也提到顶级
        new.append(line)
    new_text = '\n'.join(new)
    open(path,'w',encoding='utf-8').write(new_text)

# 准确做法：读 yaml，key 提上去，重新 dump
def lift(path):
    d = yaml.safe_load(open(path))
    if 'anti_examples' in d.get('expected_output', {}):
        d['anti_examples'] = d['expected_output'].pop('anti_examples')
    if 'grading_rubric' in d.get('expected_output', {}):
        d['grading_rubric'] = d['expected_output'].pop('grading_rubric')
    # 按标准顺序重新 dump
    order = ['id','title','category','vendor','version','difficulty','tags',
             'input','expected_output','anti_examples','grading_rubric']
    d2 = {k: d[k] for k in order if k in d}
    # 保留额外 key
    for k in d:
        if k not in d2: d2[k] = d[k]
    # block style 默认（PyYAML 用 default_flow_style=False 时会用 block）
    yaml.dump(d2, open(path,'w',encoding='utf-8'),
              default_flow_style=False, allow_unicode=True, sort_keys=False)

Q = ['NSG-Q-0019.yaml','NSG-Q-0020.yaml','NSG-Q-0021.yaml','NSG-Q-0022.yaml','NSG-Q-0023.yaml','NSG-Q-0024.yaml','NSG-Q-0025.yaml','NSG-Q-0026.yaml','NSG-Q-0027.yaml']
for q in Q:
    p='eval/dataset/'+q
    lift(p)

# 校验
err=[]
for q in Q:
    p='eval/dataset/'+q
    d=yaml.safe_load(open(p))
    must=['id','title','category','vendor','version','difficulty','tags','input','expected_output','anti_examples','grading_rubric']
    miss=[m for m in must if m not in d]
    if miss: err.append((q,'miss:'+str(miss)))
print('err:',err if err else 'NONE')
