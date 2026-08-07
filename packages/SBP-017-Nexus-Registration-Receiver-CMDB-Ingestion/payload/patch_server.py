from pathlib import Path
import re

path=Path("backend/api/server.py")
text=path.read_text()
import_line="from backend.api import seymour_registration_routes\n"

if import_line not in text:
    m=re.search(r"^class\s+\w+Handler\b",text,re.MULTILINE)
    if not m: raise SystemExit("Could not locate API handler class.")
    text=text[:m.start()]+import_line+"\n"+text[m.start():]

for method,handler in (("GET","handle_get"),("POST","handle_post")):
    marker=f"seymour_registration_routes.{handler}(self)"
    if marker in text: continue
    p=re.compile(rf"(\n    def do_{method}\(self\)(?: -> [^:]+)?:\n)")
    m=p.search(text)
    if not m: raise SystemExit(f"Could not locate do_{method}.")
    insertion=m.group(1)+f"        if seymour_registration_routes.{handler}(self):\n            return\n\n"
    text=text[:m.start()]+insertion+text[m.end():]

path.write_text(text)
print("Nexus Seymour registration routes installed.")
