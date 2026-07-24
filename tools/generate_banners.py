#!/usr/bin/env python3
"""
Banner Generator for Legion Repositories
Downloads/generates SVG banners directly into docs/assets/ to ensure 100% reliable GitHub rendering.
"""

import urllib.request
from pathlib import Path

HEADER_URL = "https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=10,18,30,42,55&height=230&section=header&text=GROK%20BUILD%20LEGION%20EDITION&fontSize=48&fontAlignY=38&desc=Universal%20Heterogeneous%20Multi-Agent%20DAG%20%7C%20100%25%20Provider%20%26%20Model%20Agnostic&descFontSize=18&descAlignY=62&animation=fadeIn"
FOOTER_URL = "https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=10,18,30,42,55&height=100&section=footer"

LEGION_BUILD_HEADER_URL = "https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=10,18,30,42,55&height=230&section=header&text=LEGION%20BUILD&fontSize=60&fontAlignY=38&desc=Universal%20Heterogeneous%20Multi-Agent%20DAG%20%7C%20100%25%20Provider%20%26%20Model%20Agnostic&descFontSize=18&descAlignY=62&animation=fadeIn"

req_headers = {"User-Agent": "Mozilla/5.0"}

def download_svg(url, dest_path):
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req) as resp:
        content = resp.read()
    with open(dest_path, "wb") as f:
        f.write(content)
    print(f"Downloaded banner SVG to {dest_path} ({len(content)} bytes)")

def main():
    repo1_docs = Path("/home/shawn5cents/Desktop/grok-build-legion-edition/grok-build-legion-edition-main/docs/assets")
    repo2_docs = Path("/home/shawn5cents/Desktop/legion-build/docs/assets")

    download_svg(HEADER_URL, repo1_docs / "banner.svg")
    download_svg(FOOTER_URL, repo1_docs / "footer.svg")

    download_svg(LEGION_BUILD_HEADER_URL, repo2_docs / "banner.svg")
    download_svg(FOOTER_URL, repo2_docs / "footer.svg")

if __name__ == "__main__":
    main()
