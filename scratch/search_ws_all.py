with open("templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()

import re
matches = re.finditer(r'ws', text, re.IGNORECASE)
count = 0
for m in matches:
    count += 1
    start = max(0, m.start() - 30)
    end = min(len(text), m.end() + 30)
    print(f"Match {count}: ...{text[start:end]}...")
    if count >= 30:
        break
