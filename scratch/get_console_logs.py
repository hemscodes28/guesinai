transcript_path = r"C:\Users\Hemkumar Ramesh\.gemini\antigravity-ide\brain\224b2043-2a51-475d-9da7-59ba894fe24a\.system_generated\logs\transcript_full.jsonl"

try:
    with open(transcript_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if "console" in line.lower() and '"source":"SYSTEM"' in line:
                print(f"Line {idx}: {line[:500]}...")
except Exception as e:
    print("Error:", e)
