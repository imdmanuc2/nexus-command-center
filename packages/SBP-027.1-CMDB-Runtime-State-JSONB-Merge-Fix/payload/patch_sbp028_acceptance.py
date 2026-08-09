from pathlib import Path

path = Path("scripts/acceptance/verify_sbp028_live_runtime_state.py")
text = path.read_text()

old = """    state = str(
        asset["observed_state"]
        or ""
    ).strip().lower()

    if state not in valid_states:
        raise SystemExit(
            "BCH asset observed_state is not normalized: "
            f"{asset['observed_state']!r}"
        )
"""

new = """    observed_state = (
        asset["observed_state"]
        if isinstance(
            asset["observed_state"],
            dict,
        )
        else {}
    )

    state = str(
        observed_state.get(
            "runtimeState",
            "",
        )
    ).strip().lower()

    if state not in valid_states:
        raise SystemExit(
            "BCH asset observed_state.runtimeState "
            "is not normalized: "
            f"{observed_state.get('runtimeState')!r}"
        )
"""

if old not in text:
    if 'observed_state.get(' in text and '"runtimeState"' in text:
        print("SBP-028 acceptance semantics already patched.")
        raise SystemExit(0)
    raise SystemExit("Expected SBP-028 observed_state verification block not found.")

path.write_text(text.replace(old, new, 1))
print("SBP-028 live acceptance JSONB semantics patched.")
