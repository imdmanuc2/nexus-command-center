import json
from pathlib import Path

import pytest

from backend.services import (
    nexus_peer_machine_identity_service
    as machine_identity,
)
from backend.services import (
    nexus_peer_pairing_credential_service
    as credential_service,
)


@pytest.fixture
def identity(
    tmp_path: Path,
    monkeypatch,
):
    key_path = (
        tmp_path
        / "private"
        / "machine.key"
    )

    key = (
        machine_identity
        .generate_private_key()
    )

    machine_identity.persist_private_key(
        key,
        path=key_path,
    )

    monkeypatch.setattr(
        machine_identity,
        "private_key_path",
        lambda: key_path,
    )

    monkeypatch.setattr(
        machine_identity,
        "load_private_key",
        lambda path=None: (
            machine_identity
            .load_private_key.__wrapped__(
                path=path
            )
            if hasattr(
                machine_identity
                .load_private_key,
                "__wrapped__",
            )
            else key
        ),
    )

    monkeypatch.setattr(
        credential_service,
        "_local_instance_id",
        lambda: "nexus-local-test",
    )

    return key_path


def _install_key(
    tmp_path: Path,
    monkeypatch,
):
    key_path = (
        tmp_path
        / "private"
        / "machine.key"
    )

    key = (
        machine_identity
        .generate_private_key()
    )

    machine_identity.persist_private_key(
        key,
        path=key_path,
    )

    original_load = (
        machine_identity
        .load_private_key
    )

    monkeypatch.setattr(
        machine_identity,
        "private_key_path",
        lambda: key_path,
    )

    monkeypatch.setattr(
        machine_identity,
        "load_private_key",
        lambda path=None: original_load(
            path=(
                path
                if path is not None
                else key_path
            )
        ),
    )

    monkeypatch.setattr(
        credential_service,
        "_local_instance_id",
        lambda: "nexus-local-test",
    )

    return key_path


def test_round_trip_is_encrypted_and_owner_only(
    tmp_path: Path,
    monkeypatch,
):
    _install_key(
        tmp_path,
        monkeypatch,
    )

    directory = (
        tmp_path
        / "credentials"
    )

    secret = (
        "one-time-enrollment-secret-value"
    )

    path = (
        credential_service
        .store_credential(
            pairing_id="pairing-test-1",
            enrollment_secret=secret,
            directory=directory,
        )
    )

    assert directory.stat().st_mode & 0o777 == 0o700
    assert path.stat().st_mode & 0o777 == 0o600

    raw = path.read_text(
        encoding="utf-8"
    )

    assert secret not in raw

    document = json.loads(raw)

    assert document["version"] == 1
    assert document["algorithm"] == "AES-256-GCM"
    assert document["keyDerivation"] == "HKDF-SHA256"

    assert (
        credential_service
        .load_credential(
            pairing_id="pairing-test-1",
            directory=directory,
        )
        == secret
    )


def test_ciphertext_is_bound_to_pairing_id(
    tmp_path: Path,
    monkeypatch,
):
    _install_key(
        tmp_path,
        monkeypatch,
    )

    directory = (
        tmp_path
        / "credentials"
    )

    first = (
        credential_service
        .store_credential(
            pairing_id="pairing-first",
            enrollment_secret="secret",
            directory=directory,
        )
    )

    second = (
        directory
        / "pairing-second.credential"
    )

    second.write_bytes(
        first.read_bytes()
    )
    second.chmod(0o600)

    with pytest.raises(
        ValueError,
        match="authentication failed",
    ):
        credential_service.load_credential(
            pairing_id="pairing-second",
            directory=directory,
        )


def test_ciphertext_is_bound_to_local_instance(
    tmp_path: Path,
    monkeypatch,
):
    _install_key(
        tmp_path,
        monkeypatch,
    )

    directory = (
        tmp_path
        / "credentials"
    )

    credential_service.store_credential(
        pairing_id="pairing-test",
        enrollment_secret="secret",
        directory=directory,
    )

    monkeypatch.setattr(
        credential_service,
        "_local_instance_id",
        lambda: "different-local-instance",
    )

    with pytest.raises(
        ValueError,
        match="authentication failed",
    ):
        credential_service.load_credential(
            pairing_id="pairing-test",
            directory=directory,
        )


def test_tampered_ciphertext_is_rejected(
    tmp_path: Path,
    monkeypatch,
):
    _install_key(
        tmp_path,
        monkeypatch,
    )

    directory = (
        tmp_path
        / "credentials"
    )

    path = (
        credential_service
        .store_credential(
            pairing_id="pairing-test",
            enrollment_secret="secret",
            directory=directory,
        )
    )

    document = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    value = document["ciphertext"]

    replacement = (
        "A"
        if value[-1] != "A"
        else "B"
    )

    document["ciphertext"] = (
        value[:-1]
        + replacement
    )

    path.write_text(
        json.dumps(document),
        encoding="utf-8",
    )
    path.chmod(0o600)

    with pytest.raises(
        ValueError,
        match="authentication failed",
    ):
        credential_service.load_credential(
            pairing_id="pairing-test",
            directory=directory,
        )


def test_duplicate_store_does_not_overwrite(
    tmp_path: Path,
    monkeypatch,
):
    _install_key(
        tmp_path,
        monkeypatch,
    )

    directory = (
        tmp_path
        / "credentials"
    )

    credential_service.store_credential(
        pairing_id="pairing-test",
        enrollment_secret="first-secret",
        directory=directory,
    )

    with pytest.raises(
        FileExistsError,
        match="already exists",
    ):
        credential_service.store_credential(
            pairing_id="pairing-test",
            enrollment_secret="second-secret",
            directory=directory,
        )

    assert (
        credential_service
        .load_credential(
            pairing_id="pairing-test",
            directory=directory,
        )
        == "first-secret"
    )


def test_delete_is_idempotent(
    tmp_path: Path,
    monkeypatch,
):
    _install_key(
        tmp_path,
        monkeypatch,
    )

    directory = (
        tmp_path
        / "credentials"
    )

    credential_service.store_credential(
        pairing_id="pairing-test",
        enrollment_secret="secret",
        directory=directory,
    )

    assert (
        credential_service
        .delete_credential(
            pairing_id="pairing-test",
            directory=directory,
        )
        is True
    )

    assert (
        credential_service
        .delete_credential(
            pairing_id="pairing-test",
            directory=directory,
        )
        is False
    )


def test_insecure_existing_directory_is_rejected(
    tmp_path: Path,
    monkeypatch,
):
    _install_key(
        tmp_path,
        monkeypatch,
    )

    directory = (
        tmp_path
        / "credentials"
    )

    directory.mkdir(
        mode=0o755
    )

    with pytest.raises(
        PermissionError,
        match="directory permissions",
    ):
        credential_service.store_credential(
            pairing_id="pairing-test",
            enrollment_secret="secret",
            directory=directory,
        )


def test_insecure_credential_file_is_rejected(
    tmp_path: Path,
    monkeypatch,
):
    _install_key(
        tmp_path,
        monkeypatch,
    )

    directory = (
        tmp_path
        / "credentials"
    )

    path = (
        credential_service
        .store_credential(
            pairing_id="pairing-test",
            enrollment_secret="secret",
            directory=directory,
        )
    )

    path.chmod(0o644)

    with pytest.raises(
        PermissionError,
        match="credential permissions",
    ):
        credential_service.load_credential(
            pairing_id="pairing-test",
            directory=directory,
        )


@pytest.mark.parametrize(
    "pairing_id",
    [
        "../escape",
        "/absolute",
        "a/b",
        "",
        " ",
    ],
)
def test_pairing_id_cannot_escape_directory(
    tmp_path: Path,
    monkeypatch,
    pairing_id,
):
    _install_key(
        tmp_path,
        monkeypatch,
    )

    with pytest.raises(ValueError):
        credential_service.store_credential(
            pairing_id=pairing_id,
            enrollment_secret="secret",
            directory=(
                tmp_path
                / "credentials"
            ),
        )


def test_plaintext_secret_not_in_document(
    tmp_path: Path,
    monkeypatch,
):
    _install_key(
        tmp_path,
        monkeypatch,
    )

    directory = (
        tmp_path
        / "credentials"
    )

    secret = (
        "highly-sensitive-one-time-secret"
    )

    path = (
        credential_service
        .store_credential(
            pairing_id="pairing-test",
            enrollment_secret=secret,
            directory=directory,
        )
    )

    assert secret not in path.read_text(
        encoding="utf-8"
    )
