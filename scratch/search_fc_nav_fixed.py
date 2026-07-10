with open("templates/index.html", "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if "forecast" in line.lower() and i < 1100:
            safe_line = line.encode('ascii', 'ignore').decode()
            print(f"Line {i}: {safe_line.strip()}")
