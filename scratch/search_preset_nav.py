import os

search_paths = [
    r"C:\Users\Hemkumar Ramesh\Desktop",
    r"C:\Users\Hemkumar Ramesh\Downloads",
]

found = []
for path in search_paths:
    if not os.path.exists(path):
        continue
    print(f"Searching in {path}...")
    for root, dirs, files in os.walk(path):
        # Skip some big directories to avoid slow search
        if "node_modules" in dirs:
            dirs.remove("node_modules")
        if ".git" in dirs:
            dirs.remove(".git")
        
        for file in files:
            if "preset-nav-fix" in file or "preset-site-routing" in file:
                found.append(os.path.join(root, file))

if found:
    print("Found matches:")
    for f in found:
        print(f)
else:
    print("No matches found.")
