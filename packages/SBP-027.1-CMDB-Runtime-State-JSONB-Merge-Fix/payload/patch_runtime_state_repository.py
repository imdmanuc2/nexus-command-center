from pathlib import Path

path = Path("backend/db/repositories/seymour_runtime_state_repository.py")
text = path.read_text()

old = """        # Make the normalized runtime state first-class on the CMDB asset.
        cur.execute(
            \"""
            UPDATE nexus.assets
            SET
                observed_state = %s,
                last_seen_at = %s
            WHERE asset_id = %s
            \""",
            (
                state,
                observed_at,
                subject_id,
            ),
        )
"""

new = """        # Preserve the rich observed_state JSON document and merge
        # normalized runtime state into it as first-class CMDB state.
        observed_patch = {
            "runtimeState": state,
            "runtimeStateReason": runtime.get("reason"),
            "runtimeRpcReachable": runtime.get("rpcReachable"),
            "runtimeRpcHealthy": runtime.get("rpcHealthy"),
            "runtimeInitialBlockDownload": runtime.get(
                "initialBlockDownload"
            ),
            "runtimeVerificationProgress": runtime.get(
                "verificationProgress"
            ),
        }

        cur.execute(
            \"""
            UPDATE nexus.assets
            SET
                observed_state =
                    COALESCE(
                        observed_state,
                        '{}'::jsonb
                    )
                    ||
                    %s,
                last_seen_at = %s
            WHERE asset_id = %s
            \""",
            (
                Jsonb(observed_patch)
                if Jsonb
                else observed_patch,
                observed_at,
                subject_id,
            ),
        )
"""

if old not in text:
    if "observed_patch = {" in text and "runtimeState" in text:
        print("SBP-027.1 JSONB merge semantics already present.")
        raise SystemExit(0)
    raise SystemExit("Expected SBP-027 observed_state update block not found.")

path.write_text(text.replace(old, new, 1))
print("SBP-027.1 observed_state JSONB merge semantics patched.")
