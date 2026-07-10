with open("templates/index.html", "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if "clearscenariopreview" in line.lower():
            print(f"Line {i}: {line.strip()}")
