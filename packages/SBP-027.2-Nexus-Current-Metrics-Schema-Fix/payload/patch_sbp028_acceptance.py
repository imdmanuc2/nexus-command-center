from pathlib import Path

path = Path("scripts/acceptance/verify_sbp028_live_runtime_state.py")
text = path.read_text()

text = text.replace(
'''EXPECTED_METRICS = {
    "runtime.state",
    "runtime.rpc.reachable",
    "runtime.rpc.healthy",
    "runtime.initial_block_download",
    "runtime.verification_progress",
}
''',
'''EXPECTED_METRICS = {
    "runtime.rpc.reachable",
    "runtime.rpc.healthy",
    "runtime.initial_block_download",
    "runtime.verification_progress",
}
''',
)

start = text.find('    state_metric = next(')
if start != -1:
    end_marker = '        )\n'
    # remove through the end of the mismatch check block
    tail = text.find('    print(', start)
    if tail != -1:
        text = text[:start] + '    # runtimeState is canonical in observed_state JSONB.\n\n' + text[tail:]

path.write_text(text)
print("SBP-028 acceptance updated for canonical runtimeState location.")
