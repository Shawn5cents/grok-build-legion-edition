#!/usr/bin/env python3
from pathlib import Path

docs_dir = Path("/home/shawn5cents/Desktop/grok-build-legion-edition/grok-build-legion-edition-main/docs/assets")

for name in ["banner.svg", "footer.svg"]:
    svg_file = docs_dir / name
    if svg_file.exists():
        content = svg_file.read_text().strip()
        if not content.startswith("<?xml"):
            content = '<?xml version="1.0" encoding="UTF-8"?>\n' + content
        svg_file.write_text(content)
        print(f"Fixed {name}: cleaned leading whitespace and added XML declaration header.")
