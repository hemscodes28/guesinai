import re

with open("templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()

matches = re.finditer(r'fetch\([^\)]+\)', text)
for i, m in enumerate(matches, 1):
    print(f"Fetch {i}: {m.group(0)}")
