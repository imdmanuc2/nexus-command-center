from __future__ import annotations

from unittest.mock import Mock

import pytest

from backend.services import (
    nexus_peer_pairing_status_service as service,
)


PAIRING = "pairing-test"
LOCAL = "nexus-local"
REMOTE = "nexus-remote"
ENROLLMENT = "enrollment-test"
BASE_URL = "http://remote:8561"


def _row(
    status: str = "pending",
) -> dict:
    return {
        "pairing_id": PAIRING,
        "local_instance_id": LOCAL,
        "remote_instance_id": REMOTE,
        "remote_enrollment_id": ENROLLMENT,
        "peer_base_url": BASE_URL,
        "status": status,
    }


def _response(
    status: str,
) -> dict:
    return {
        "status": status,
        "enrollmentId": ENROLLMENT,
        "pairingId": PAIRING,
        "localInstanceId": REMOTE,
        "remoteInstanceId": LOCAL,
    }


def _install_pairing(
    monkeypatch,
    *,
    status: str = "pending",
):
    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "get_pairing",
        lambda pairing_id: _row(status),
    )


def test_pending_remote_status_does_not_transition(
    monkeypatch,
):
    _install_pairing(
        monkeypatch,
    )

    transition = Mock(
        side_effect=AssertionError(
            "pending status must not transition"
        )
    )

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "transition_pairing",
        transition,
    )

    requester = Mock(
        return_value=_response(
            "pending"
        )
    )

    result = service.reconcile_pairing_status(
        pairing_id=PAIRING,
        status_requester=requester,
    )

    assert result == {
        "status": "pending",
        "pairingId": PAIRING,
        "remoteInstanceId": REMOTE,
        "remoteEnrollmentId": ENROLLMENT,
        "remoteStatus": "pending",
        "changed": False,
    }

    requester.assert_called_once_with(
        remote_instance_id=REMOTE,
        peer_base_url=BASE_URL,
        enrollment_id=ENROLLMENT,
        pairing_id=PAIRING,
        timeout=(
            service
            .nexus_peer_enrollment_client_service
            .DEFAULT_TIMEOUT_SECONDS
        ),
    )

    transition.assert_not_called()


@pytest.mark.parametrize(
    "remote_status",
    [
        "approved",
        "rejected",
        "expired",
    ],
)
def test_terminal_receiver_decision_uses_atomic_transition(
    monkeypatch,
    remote_status,
):
    _install_pairing(
        monkeypatch,
    )

    requester = Mock(
        return_value=_response(
            remote_status
        )
    )

    transition = Mock(
        return_value=_row(
            remote_status
        )
    )

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "transition_pairing",
        transition,
    )

    result = service.reconcile_pairing_status(
        pairing_id=PAIRING,
        status_requester=requester,
    )

    transition.assert_called_once_with(
        pairing_id=PAIRING,
        expected_status="pending",
        new_status=remote_status,
    )

    assert result["status"] == remote_status
    assert result["remoteStatus"] == remote_status
    assert result["changed"] is True


def test_used_receiver_state_is_protocol_error_without_transition(
    monkeypatch,
):
    _install_pairing(
        monkeypatch,
    )

    transition = Mock()

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "transition_pairing",
        transition,
    )

    with pytest.raises(
        RuntimeError,
        match="already used",
    ):
        service.reconcile_pairing_status(
            pairing_id=PAIRING,
            status_requester=Mock(
                return_value=_response(
                    "used"
                )
            ),
        )

    transition.assert_not_called()


@pytest.mark.parametrize(
    "status",
    [
        "approved",
        "rejected",
        "expired",
    ],
)
def test_already_reconciled_state_is_idempotent_without_network(
    monkeypatch,
    status,
):
    _install_pairing(
        monkeypatch,
        status=status,
    )

    requester = Mock(
        side_effect=AssertionError(
            "terminal reconciliation must not use network"
        )
    )

    transition = Mock(
        side_effect=AssertionError(
            "terminal reconciliation must not transition"
        )
    )

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "transition_pairing",
        transition,
    )

    result = service.reconcile_pairing_status(
        pairing_id=PAIRING,
        status_requester=requester,
    )

    assert result["status"] == status
    assert result["changed"] is False

    requester.assert_not_called()
    transition.assert_not_called()


@pytest.mark.parametrize(
    "status",
    [
        "requesting",
        "completing",
        "connected",
        "failed",
    ],
)
def test_non_pending_non_reconciled_state_is_rejected_before_network(
    monkeypatch,
    status,
):
    _install_pairing(
        monkeypatch,
        status=status,
    )

    requester = Mock()

    with pytest.raises(
        PermissionError,
        match="not pending approval",
    ):
        service.reconcile_pairing_status(
            pairing_id=PAIRING,
            status_requester=requester,
        )

    requester.assert_not_called()


def test_missing_pairing_is_rejected(
    monkeypatch,
):
    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "get_pairing",
        lambda pairing_id: None,
    )

    with pytest.raises(
        KeyError,
        match="Outbound pairing not found",
    ):
        service.reconcile_pairing_status(
            pairing_id=PAIRING,
            status_requester=Mock(),
        )


def test_empty_pairing_id_is_rejected_before_repository(
    monkeypatch,
):
    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "get_pairing",
        Mock(
            side_effect=AssertionError(
                "repository must not be touched"
            )
        ),
    )

    with pytest.raises(
        ValueError,
        match="pairingId is required",
    ):
        service.reconcile_pairing_status(
            pairing_id="",
            status_requester=Mock(),
        )


@pytest.mark.parametrize(
    ("field", "message"),
    [
        (
            "enrollmentId",
            "enrollment mismatch",
        ),
        (
            "pairingId",
            "pairing mismatch",
        ),
        (
            "localInstanceId",
            "remote Nexus mismatch",
        ),
        (
            "remoteInstanceId",
            "requester mismatch",
        ),
    ],
)
def test_response_identity_mismatch_does_not_transition(
    monkeypatch,
    field,
    message,
):
    _install_pairing(
        monkeypatch,
    )

    response = _response(
        "approved"
    )

    response[field] = "wrong"

    transition = Mock()

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "transition_pairing",
        transition,
    )

    with pytest.raises(
        RuntimeError,
        match=message,
    ):
        service.reconcile_pairing_status(
            pairing_id=PAIRING,
            status_requester=Mock(
                return_value=response
            ),
        )

    transition.assert_not_called()


def test_invalid_response_type_does_not_transition(
    monkeypatch,
):
    _install_pairing(
        monkeypatch,
    )

    transition = Mock()

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "transition_pairing",
        transition,
    )

    with pytest.raises(
        RuntimeError,
        match="invalid response",
    ):
        service.reconcile_pairing_status(
            pairing_id=PAIRING,
            status_requester=Mock(
                return_value=None
            ),
        )

    transition.assert_not_called()


def test_reconciliation_never_invokes_completion(
    monkeypatch,
):
    _install_pairing(
        monkeypatch,
    )

    transition = Mock(
        return_value=_row(
            "approved"
        )
    )

    monkeypatch.setattr(
        service.nexus_peer_outbound_pairing_repository,
        "transition_pairing",
        transition,
    )

    result = service.reconcile_pairing_status(
        pairing_id=PAIRING,
        status_requester=Mock(
            return_value=_response(
                "approved"
            )
        ),
    )

    assert result["status"] == "approved"
    assert result["changed"] is True
