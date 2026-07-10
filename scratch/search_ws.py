with open("templates/index.html", "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if "websocket" in line.lower() or "onmessage" in line.lower() or "socket" in line.lower() or "host" in line.lower():
            print(f"Line {i}: {line.strip()[:100]}")
