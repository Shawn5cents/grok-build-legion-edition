#!/usr/bin/env python3
"""
Generate Pristine XML-Compliant SVG Header & Footer Banners for Grok Build Legion Edition
Escapes all raw '&' into '&amp;' to prevent 'xmlParseEntityRef: no name' XML errors.
"""

import urllib.request
import re
from pathlib import Path

HEADER_URL = "https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=10,18,30,42,55&height=230&section=header&text=%E2%9A%94%EF%B8%8F%20GROK%20BUILD%20LEGION%20EDITION&fontSize=46&fontAlignY=38&desc=Universal%20Heterogeneous%20Multi-Agent%20DAG%20%7C%20100%25%20Provider%20%26%20Model%20Agnostic&descFontSize=18&descAlignY=62&animation=fadeIn"
FOOTER_URL = "https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=10,18,30,42,55&height=100&section=footer"

req_headers = {"User-Agent": "Mozilla/5.0"}

def download_and_sanitize_svg(url, dest_path):
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req) as resp:
        raw_svg = resp.read().decode("utf-8")
    
    # Clean leading whitespace
    cleaned = raw_svg.strip()
    
    # Fix unescaped '&' characters into '&amp;' for valid XML parsing
    # Replace & that is NOT already &amp;, &lt;, &gt;, &quot;, &apos;, or &#...;
    sanitized = re.sub(r'&(?!(amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)', '&amp;', cleaned)
    
    if not sanitized.startswith("<?xml"):
        sanitized = '<?xml version="1.0" encoding="UTF-8"?>\n' + sanitized

    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(sanitized)
    print(f"Sanitized & saved valid XML SVG to {dest_path}")

def main():
    dest_dir = Path("/home/shawn5cents/Desktop/grok-build-legion-edition/grok-build-legion-edition-main/docs/assets")
    download_and_sanitize_svg(HEADER_URL, dest_dir / "banner.svg")
    download_and_sanitize_svg(FOOTER_URL, dest_dir / "footer.svg")

if __name__ == "__main__":
    main()
