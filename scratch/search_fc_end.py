with open("templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()

import re
matches = [m.start() for m in re.finditer(r'<div class="modal-overlay" id="forecast-modal">', text)]
if matches:
    start_pos = matches[0]
    # find next <div class="modal-overlay" or script tags
    end_matches = [m.start() for m in re.finditer(r'<!-- ', text[start_pos:])]
    for em in end_matches[:5]:
        print(f"End match sample: {text[start_pos + em : start_pos + em + 100]}")
