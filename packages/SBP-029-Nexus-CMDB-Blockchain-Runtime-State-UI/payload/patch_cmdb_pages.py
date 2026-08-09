from pathlib import Path

targets = [
    Path("frontend/assets.html"),
    Path("frontend/cmdb-object.html"),
]

css = '<link rel="stylesheet" href="/css/cmdb-runtime-state.css">'
js = '<script src="/js/cmdb-runtime-state.js"></script>'

for path in targets:
    if not path.exists():
        raise SystemExit(f"Missing CMDB page: {path}")

    text = path.read_text()

    if css not in text:
        if "</head>" not in text:
            raise SystemExit(f"Could not locate </head> in {path}")
        text = text.replace(
            "</head>",
            f"  {css}\n</head>",
            1,
        )

    if js not in text:
        if "</body>" not in text:
            raise SystemExit(f"Could not locate </body> in {path}")
        text = text.replace(
            "</body>",
            f"  {js}\n</body>",
            1,
        )

    path.write_text(text)
    print(f"SBP-029 runtime-state UI wired: {path}")
