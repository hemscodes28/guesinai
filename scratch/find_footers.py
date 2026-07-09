with open("templates/index.html", "r", encoding="utf-8") as f:
    for idx, line in enumerate(f, 1):
        if "footer" in line.lower() or "rights reserved" in line.lower():
            print(f"Line {idx}: {line.strip()}")
