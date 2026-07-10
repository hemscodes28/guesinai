import os

for root, dirs, files in os.walk("."):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if "get_recovery_scores" in content:
                    print(f"Match in {path}")
                    for i, line in enumerate(content.split("\n"), 1):
                        if "get_recovery_scores" in line:
                            print(f"  Line {i}: {line.strip()}")
