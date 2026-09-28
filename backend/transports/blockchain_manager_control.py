from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
import json
import re
import ssl
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


_PROVIDER_ID_RE = re.compile(
    r"^[a-z0-9][a-z0-9-]{0,63}$"
)

_STORAGE_TARGET_ID_RE = re.compile(
    r"^[A-Za-z0-9_.:-]{1,128}$"
)


class BlockchainManagerControlError(
    RuntimeError
):
    pass


@dataclass(frozen=True, slots=True)
class BlockchainManagerInstallRequest:
    provider_id: str
    storage_target_id: str
    storage_source: str
    storage_filesystem: str


@dataclass(frozen=True, slots=True)
class BlockchainManagerInstallResult:
    operation_id: str
    status: str
    provider_id: str
    storage_target_id: str
    verified: bool
    duration_ms: int
    result: dict[str, Any]


class BlockchainManagerControlTransport:
    """
    Typed HTTP transport for Nexus -> Seymour Blockchain Manager.

    The transport owns no SSH, filesystem path, Umbrel lifecycle,
    RPC credential, app identity, port, or confirmation-token input.

    Nexus supplies only:
      - provider identity
      - approved storage target identity

    Blockchain Manager remains the target-side execution authority.
    """

    def __init__(
        self,
        *,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        self._opener = opener

    @staticmethod
    def _provider_id(value: str) -> str:
        normalized = str(value or "").strip()

        if not _PROVIDER_ID_RE.fullmatch(
            normalized
        ):
            raise ValueError(
                "Invalid provider_id"
            )

        return normalized

    @staticmethod
    def _storage_target_id(
        value: str,
    ) -> str:
        normalized = str(value or "").strip()

        if not _STORAGE_TARGET_ID_RE.fullmatch(
            normalized
        ):
            raise ValueError(
                "Invalid storage_target_id"
            )

        return normalized

    @staticmethod
    def _endpoint(value: str) -> str:
        endpoint = str(value or "").strip()

        if not endpoint:
            raise ValueError(
                "Blockchain Manager endpoint is required"
            )

        if not endpoint.startswith("https://"):
            raise ValueError(
                "Blockchain Manager endpoint must use HTTPS"
            )

        return endpoint.rstrip("/")

    @staticmethod
    def _token(value: str) -> str:
        token = str(value or "").strip()

        if not token:
            raise ValueError(
                "Blockchain Manager control token is required"
            )

        return token

    def install(
        self,
        *,
        endpoint: str,
        token: str,
        ssl_context: ssl.SSLContext,
        request: BlockchainManagerInstallRequest,
        timeout_seconds: int = 900,
    ) -> BlockchainManagerInstallResult:
        if timeout_seconds <= 0:
            raise ValueError(
                "Blockchain Manager timeout must be positive"
            )

        endpoint = self._endpoint(
            endpoint
        )

        token = self._token(
            token
        )

        if not isinstance(
            ssl_context,
            ssl.SSLContext,
        ):
            raise ValueError(
                "Blockchain Manager verified TLS context is required"
            )

        if (
            ssl_context.verify_mode
            != ssl.CERT_REQUIRED
            or ssl_context.check_hostname is not True
        ):
            raise ValueError(
                "Blockchain Manager TLS context "
                "must require certificate and hostname verification"
            )

        provider_id = self._provider_id(
            request.provider_id
        )

        storage_target_id = (
            self._storage_target_id(
                request.storage_target_id
            )
        )

        storage_source = str(
            request.storage_source or ""
        ).strip()

        storage_filesystem = str(
            request.storage_filesystem or ""
        ).strip()

        if not storage_source:
            raise ValueError(
                "Invalid storage_source"
            )

        if not storage_filesystem:
            raise ValueError(
                "Invalid storage_filesystem"
            )

        body = json.dumps({
            "providerId": provider_id,
            "storageTargetId": storage_target_id,
            "storageIdentity": {
                "source": storage_source,
                "filesystem": storage_filesystem,
            },
        }).encode("utf-8")

        outbound = Request(
            endpoint
            + "/api/nexus/install/execute",
            data=body,
            headers={
                "Authorization":
                    f"Bearer {token}",
                "Content-Type":
                    "application/json",
                "Accept":
                    "application/json",
                "User-Agent":
                    "Nexus-Blockchain-Control/1.0",
            },
            method="POST",
        )

        started = time.monotonic()

        try:
            with self._opener(
                outbound,
                timeout=timeout_seconds,
                context=ssl_context,
            ) as response:
                raw = response.read().decode(
                    "utf-8"
                )

                http_status = int(
                    response.status
                )

        except HTTPError as exc:
            try:
                raw = exc.read().decode(
                    "utf-8"
                )
            except Exception:
                raw = ""

            message = (
                "Blockchain Manager returned HTTP "
                f"{exc.code}"
            )

            if raw:
                try:
                    payload = json.loads(raw)

                    detail = str(
                        payload.get("error")
                        or payload.get("message")
                        or ""
                    ).strip()

                    if detail:
                        message += f": {detail}"

                except Exception:
                    pass

            raise BlockchainManagerControlError(
                message
            ) from exc

        except URLError as exc:
            raise BlockchainManagerControlError(
                "Blockchain Manager request failed"
            ) from exc

        except TimeoutError as exc:
            raise BlockchainManagerControlError(
                "Blockchain Manager request timed out"
            ) from exc

        except Exception as exc:
            raise BlockchainManagerControlError(
                "Blockchain Manager request failed"
            ) from exc

        if not (
            HTTPStatus.OK
            <= http_status
            < HTTPStatus.MULTIPLE_CHOICES
        ):
            raise BlockchainManagerControlError(
                "Blockchain Manager returned unexpected status"
            )

        try:
            payload = json.loads(raw)
        except Exception as exc:
            raise BlockchainManagerControlError(
                "Blockchain Manager returned invalid JSON"
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise BlockchainManagerControlError(
                "Blockchain Manager returned invalid result"
            )

        operation_id = str(
            payload.get("operationId")
            or ""
        ).strip()

        if not operation_id:
            raise BlockchainManagerControlError(
                "Blockchain Manager result is missing operationId"
            )

        status = str(
            payload.get("status")
            or ""
        ).strip()

        if status != "succeeded":
            raise BlockchainManagerControlError(
                "Blockchain Manager installation did not succeed"
            )

        verification = payload.get(
            "verification"
        )

        if not isinstance(
            verification,
            dict,
        ):
            raise BlockchainManagerControlError(
                "Blockchain Manager result is missing verification"
            )

        if (
            verification.get("verified")
            is not True
        ):
            raise BlockchainManagerControlError(
                "Blockchain Manager installation was not verified"
            )

        duration_ms = max(
            0,
            int(
                (
                    time.monotonic()
                    - started
                )
                * 1000
            ),
        )

        return BlockchainManagerInstallResult(
            operation_id=operation_id,
            status=status,
            provider_id=provider_id,
            storage_target_id=storage_target_id,
            verified=True,
            duration_ms=duration_ms,
            result=payload,
        )
