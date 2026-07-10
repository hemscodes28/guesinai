with open("templates/index.html", "r", encoding="utf-8") as f:
    html = f.read()

import re
scripts = re.findall(r'<script>(.*?)</script>', html, re.DOTALL)
print(f"Found {len(scripts)} script blocks.")
for idx, script in enumerate(scripts):
    print(f"\n--- Script Block {idx} (first 20 lines) ---")
    lines = script.strip().split("\n")
    for line in lines[:40]:
        print(line)
