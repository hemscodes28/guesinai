with open("simulation.py", "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if "recovery_score" in line:
            print(f"Line {i}: {line.strip()}")
