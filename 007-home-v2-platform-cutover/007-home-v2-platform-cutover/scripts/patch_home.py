from pathlib import Path
path = Path("frontend/home-v2.html")
text = path.read_text(encoding="utf-8")
tag = '<script src="/js/nexus-platform-home.js"></script>'
if tag in text:
    print("Already registered.")
    raise SystemExit(0)
for anchor in (
    '<script src="/js/home-v2.js"></script>',
    "<script src='/js/home-v2.js'></script>",
    '<script src="js/home-v2.js"></script>',
    "<script src='js/home-v2.js'></script>",
):
    if anchor in text:
        path.write_text(text.replace(anchor, tag + "\n  " + anchor, 1), encoding="utf-8")
        print("Registered Platform adapter.")
        break
else:
    raise SystemExit("Could not find home-v2.js script tag.")
