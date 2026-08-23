"""修复 scripts/fix_yaml_rubric.py 错把它误改的多元素 Yaml inline arrays 拆开。
逻辑：找到 `  - "X", "Y", "Z"` 这种没正确缩进的、原本应该拆开的位置改成多行。
"""
import os, re, yaml

QFILES = sorted([f for f in os.listdir('eval/dataset') if f.endswith('.yaml')])

for q in QFILES:
    p = 'eval/dataset/' + q
    text = open(p, encoding='utf-8').read()
    # 修复：行内逗号分隔的元素 形如 '  - "X", "Y"' 拆成多条
    pattern = re.compile(r'^(\s*)- ("[^"]*"), ("[^"]*")$', re.M)
    new_text = pattern.sub(r'\1- \2\n\1- \3', text)
    # 处理 3 个元素以上
    pattern3 = re.compile(r'^(\s*)- ("[^"]*"), ("[^"]*"), ("[^"]*")$', re.M)
    def repl3(m):
        return f"{m.group(1)}- {m.group(2)}\n{m.group(1)}- {m.group(3)}\n{m.group(1)}- {m.group(4)}"
    new_text = pattern3.sub(repl3, new_text)
    if new_text != text:
        open(p, 'w', encoding='utf-8').write(new_text)

# 校验
err = []
for q in QFILES:
    p = 'eval/dataset/' + q
    try:
        d = yaml.safe_load(open(p))
        if not isinstance(d, dict): err.append((p, f'not dict: {type(d)}')); continue
        must = ['id','title','category','vendor','version','difficulty','tags','input','expected_output','anti_examples','grading_rubric']
        miss = [m for m in must if m not in d]
        if miss: err.append((p, 'miss:'+str(miss))); continue
        rc = d['expected_output'].get('root_causes', [])
        if not isinstance(rc, list) or len(rc) < 3:
            err.append((p, f'root_causes<3:{len(rc) if isinstance(rc, list) else "NOT-LIST"}'))
    except Exception as e:
        err.append((p, f'PARSE: {str(e)[:160]}'))

print('err:', err if err else 'NONE')
print('total:', len(QFILES))
