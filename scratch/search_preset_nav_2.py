import os

search_paths = [
    r"C:\Users\Hemkumar Ramesh\.gemini",
    r"C:\Users\Hemkumar Ramesh\Desktop",
    r"C:\Users\Hemkumar Ramesh\Downloads",
]

found = []
for path in search_paths:
    if not os.path.exists(path):
        continue
    for root, dirs, files in os.walk(path):
        for file in files:
            if "preset-nav-fix" in file or "preset-nav" in file:
                found.append(os.path.join(root, file))

if found:
    print("Found matches:")
    for f in found:
        print(f)
else:
    print("No matches found.")
