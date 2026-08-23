import os, re, yaml

# 修复 must_have/penalty 中含括号斜杠导致 YAML flow-style 解析报错问题
QFILES = sorted([f for f in os.listdir('eval/dataset') if f.endswith('.yaml')])
err=[]
for q in QFILES:
    p='eval/dataset/'+q
    text = open(p, encoding='utf-8').read()
    # 把 [ "string with / or ( )" ] 形式换成 block scalar：
    # 把每一行 ["..."] 改成:
    #   key:
    #     - "..."
    new_lines=[]
    for line in text.splitlines(keepends=False):
        m = re.match(r'^(\s*)(must_have|nice_to_have|penalty):\s*\[\s*"(.+)"\s*\]', line)
        m2 = re.match(r'^(\s*)(must_have|nice_to_have|penalty):\s*\[\s*"(.+)"\s*,"(.+)"\s*\]', line)
        if m:
            indent, key, body = m.group(1), m.group(2), m.group(3)
            new_lines.append(f'{indent}{key}:')
            new_lines.append(f'{indent}  - "{body}"')
        elif m2:
            indent, key, b1, b2 = m2.group(1), m2.group(2), m2.group(3), m2.group(4)
            new_lines.append(f'{indent}{key}:')
            new_lines.append(f'{indent}  - "{b1}"')
            new_lines.append(f'{indent}  - "{b2}"')
        else:
            new_lines.append(line)
    new_text = '\n'.join(new_lines) + '\n'
    open(p, 'w', encoding='utf-8').write(new_text)
    # 再校验
    try:
        d = yaml.safe_load(open(p))
        must=['id','title','category','vendor','version','difficulty','tags','input','expected_output','anti_examples','grading_rubric']
        miss=[m for m in must if m not in d]
        if miss: err.append((p,'miss:'+str(miss)))
        rc = d['expected_output'].get('root_causes',[])
        if len(rc) < 3:
            err.append((p,'root_causes<3:'+str(len(rc))))
    except Exception as e:
        err.append((p, str(e)[:150]))

print('err:', err if err else 'NONE')
print('total:', len(QFILES))
