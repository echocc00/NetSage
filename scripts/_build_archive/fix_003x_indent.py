"""修正 NSG-Q-0031/0032/0033 三个文件的缩进：
- references 在 expected_output 内应该用 4 空格缩进（被我写成 2 空格，与 anti_examples 同级）
- anti_examples 和 grading_rubric 应是顶级（0 空格），不是 2 空格
"""
import re, yaml

FILES = ['NSG-Q-0031.yaml', 'NSG-Q-0032.yaml', 'NSG-Q-0033.yaml']

def fix(path):
    txt = open(path, encoding='utf-8').read()
    lines = txt.split('\n')
    new = []
    state = 0  # 0=normal, 1=in-expected_output, 2=after-references
    in_eo = False
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        # 进/出 expected_output
        if stripped.startswith('expected_output:'):
            in_eo = True
            new.append(line)
            continue
        # 离开 expected_output 的标志：0 缩进的 non-blank
        if in_eo:
            # 检测 references 的开始（2 空格）
            if line == '  references:':
                # 已经是 2 空格但应该是 4 空格 - 改造
                new.append('    references:')
                continue
            # 在 references 块内（4 空格缩进）
            if line.startswith('    ') and not line.startswith('      '):
                # 这里其实是 references 内部位置，但我们现在已经 indent 应该是 6 空格
                # 简单粗暴：缩进 +2
                new.append('  ' + line)
                continue
            if line.startswith('  ') and not line.startswith('  -') and not line.startswith('    '):
                # 这是 references 的兄弟「缩进错位的 anti_examples」
                # 缩进为 0，作为顶级键
                if stripped.startswith(('anti_examples:', 'grading_rubric:')):
                    new.append(stripped)
                    in_eo = False  # 退出 expected_output
                    continue
                else:
                    new.append(line)
                    continue
            # 空行
            if not line.strip():
                new.append(line)
                continue
            # references 数组内（6 空格列表项）
            if line.startswith('      -') or line.startswith('        '):
                new.append('  ' + line if line.startswith('      ') is False else line)
                continue
            # 普通 lines
            new.append(line)
        else:
            new.append(line)
    open(path, 'w', encoding='utf-8').write('\n'.join(new))

for f in FILES:
    p = f'eval/dataset/{f}'
    fix(p)

# 校验
for f in FILES:
    p = f'eval/dataset/{f}'
    d = yaml.safe_load(open(p))
    print(f'{f}: keys={sorted(d.keys())}, root_causes={len(d["expected_output"]["root_causes"])}, ae={len(d.get("anti_examples",[]))}, gr={len(d.get("grading_rubric",{}) or {})} keys={sorted((d.get("grading_rubric") or {}).keys())}')
