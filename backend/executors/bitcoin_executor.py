from __future__ import annotations

import time
from typing import Any

from backend.executors.base_executor import BaseExecutor
from backend.executors.results import ExecutionResult
from backend.modules import blockchain
from backend.modules.operations import bitcoin_rpc_test


class BitcoinExecutor(BaseExecutor):
    name = "bitcoin"

    ACTIONS = {
        "test-blockchain-rpc",
        "bitcoin.check-sync",
        "bitcoin.verify-wallet",
        "bitcoin.collect-diagnostics",
    }

    def supports(self, action_id: str, run: dict[str, Any]) -> bool:
        return action_id in self.ACTIONS

    @staticmethod
    def _target(run: dict[str, Any]) -> dict[str, Any]:
        payload = run.get("inputPayload") or {}
        entity_id = str(run.get("entityId") or "").strip()
        target = {
            "assetId": payload.get("assetId") or entity_id,
            "host": payload.get("host"),
            "coin": payload.get("coin") or "BTC",
        }
        return {key: value for key, value in target.items() if value}

    @staticmethod
    def _resolve_node(run: dict[str, Any]) -> dict[str, Any]:
        target = BitcoinExecutor._target(run)
        items = blockchain.nodes().get("items", [])

        for key in ("assetId", "host"):
            value = str(target.get(key) or "")
            if value:
                for node in items:
                    if str(node.get(key) or "") == value:
                        return node

        if len(items) == 1:
            return items[0]

        raise RuntimeError(
            "Unable to resolve the requested Bitcoin node. "
            "Provide its assetId or host in inputPayload."
        )

    def execute(self, run: dict[str, Any]) -> ExecutionResult:
        self.validate(run)
        started = time.perf_counter()
        action_id = run["actionId"]

        if action_id == "test-blockchain-rpc":
            payload = bitcoin_rpc_test(self._target(run))
            status = "completed" if payload.get("status") == "pass" else "failed"
            summary = payload.get("summary") or "Bitcoin RPC test completed."
            details = payload
        elif action_id == "bitcoin.check-sync":
            node = self._resolve_node(run)
            blocks = int(node.get("blocks") or node.get("blockHeight") or 0)
            headers = int(node.get("headers") or 0)
            ibd = bool(node.get("initialBlockDownload"))
            synced = bool(node.get("rpcConnected")) and not ibd and blocks >= headers
            status = "completed" if synced else "failed"
            summary = (
                "Bitcoin node is synchronized."
                if synced
                else "Bitcoin node is not fully synchronized."
            )
            details = {
                "assetId": node.get("assetId"),
                "host": node.get("host"),
                "rpcConnected": node.get("rpcConnected"),
                "blocks": blocks,
                "headers": headers,
                "syncPercent": node.get("syncPercent"),
                "initialBlockDownload": ibd,
                "peerCount": node.get("peerCount"),
            }
        elif action_id == "bitcoin.verify-wallet":
            node = self._resolve_node(run)
            configured = next(
                (
                    item
                    for item in blockchain._load_config()
                    if str(item.get("assetId") or "") == str(node.get("assetId") or "")
                    or str(item.get("host") or "") == str(node.get("host") or "")
                ),
                None,
            )
            if configured is None:
                raise RuntimeError("Bitcoin node configuration could not be resolved.")
            wallets = blockchain._rpc_call(configured, "listwallets") or []
            expected = str((run.get("inputPayload") or {}).get("wallet") or "").strip()
            available = expected in wallets if expected else bool(wallets)
            status = "completed" if available else "failed"
            summary = (
                f"Wallet {expected} is loaded."
                if expected and available
                else "At least one Bitcoin wallet is loaded."
                if available
                else "No loaded Bitcoin wallet matched the request."
            )
            details = {
                "assetId": node.get("assetId"),
                "walletCount": len(wallets),
                "wallets": wallets,
                "expectedWallet": expected or None,
            }
        else:
            node = self._resolve_node(run)
            details = {
                key: node.get(key)
                for key in (
                    "assetId", "name", "host", "rpcPort", "rpcConnected",
                    "chain", "blocks", "headers", "syncPercent",
                    "initialBlockDownload", "peerCount", "version",
                    "subversion", "networkActive", "mempoolSize",
                    "mempoolBytes", "sizeOnDisk", "pruned", "warnings",
                    "checkedAt",
                )
            }
            status = "completed" if node.get("rpcConnected") else "failed"
            summary = "Bitcoin diagnostics collected."

        duration_ms = round((time.perf_counter() - started) * 1000)
        return ExecutionResult(
            status=status,
            executor=self.name,
            action=action_id,
            entity_type=run["entityType"],
            entity_id=run["entityId"],
            summary=summary,
            details=details,
            duration_ms=duration_ms,
        )
