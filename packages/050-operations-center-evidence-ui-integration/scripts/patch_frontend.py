#!/usr/bin/env python3

from pathlib import Path
import shutil

PACKAGE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_DIR.parents[1]
FRONTEND = REPO_ROOT / "frontend"


def backup(path):
    backup_path = path.with_suffix(path.suffix + ".before-package-050")
    if path.exists() and not backup_path.exists():
        shutil.copy2(path, backup_path)


# ----------------------------------------------------
# Patch nav.js
# ----------------------------------------------------

nav = FRONTEND / "js" / "nav.js"

if nav.exists():
    backup(nav)

    text = nav.read_text()

    if "operations-center.html" not in text:
        text += """

document.addEventListener("DOMContentLoaded", () => {
    const nav =
        document.querySelector("nav") ||
        document.getElementById("nexusNav");

    if (!nav) return;
    if (nav.querySelector('a[href="/operations-center.html"]')) return;

    const a = document.createElement("a");
    a.href = "/operations-center.html";
    a.textContent = "Operations Center";

    nav.appendChild(a);
});
"""
        nav.write_text(text)

# ----------------------------------------------------
# Patch Home V2
# ----------------------------------------------------

home = FRONTEND / "home-v2.html"

if home.exists():
    backup(home)

    text = home.read_text()

    if "home-v2-evidence.css" not in text:
        text = text.replace(
            "</head>",
            '  <link rel="stylesheet" href="/css/home-v2-evidence.css">\n</head>'
        )

    if "home-v2-evidence.js" not in text:
        text = text.replace(
            "</body>",
            '  <script src="/js/evidence-client.js"></script>\n'
            '  <script src="/js/home-v2-evidence.js"></script>\n'
            '</body>'
        )

    home.write_text(text)

print("Package 050 frontend patched")
