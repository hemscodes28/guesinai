with open("templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()

import re
matches = re.finditer(r'forecast|runForecast|clearForecast|fc-', text, re.IGNORECASE)
printed = set()
for m in matches:
    # get line number
    line_no = text[:m.start()].count("\n") + 1
    if line_no > 1530 and line_no not in printed:
        printed.add(line_no)
        line_text = text.split("\n")[line_no - 1].strip()
        print(f"Line {line_no}: {line_text[:120]}")
