import sys
sys.stdout.reconfigure(encoding='utf-8')
with open('templates/index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines, 1):
    l = line.lower()
    if any(t in l for t in ['what-if', 'whatif', 'sitrep', 'sit-rep', 'reforest', 'tab-btn', 'toolbar', 'showpage', 'show_page', 'show-page']):
        print(f'Line {i}: {line.rstrip()[:130]}')
