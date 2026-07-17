from pathlib import Path
path = Path("frontend/graph.html")
text = path.read_text(encoding="utf-8")
tag = '<script src="/js/nexus-platform-explorer.js"></script>'
if tag in text:
    print("Already registered.")
    raise SystemExit(0)
for anchor in (
    '<script src="/js/graph.js"></script>',
    "<script src='/js/graph.js'></script>",
    '<script src="js/graph.js"></script>',
    "<script src='js/graph.js'></script>",
):
    if anchor in text:
        path.write_text(text.replace(anchor, tag + "\n  " + anchor, 1), encoding="utf-8")
        print("Registered Explorer Platform adapter.")
        break
else:
    raise SystemExit("Could not find graph.js script tag.")
