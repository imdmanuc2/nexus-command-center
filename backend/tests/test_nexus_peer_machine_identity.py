from pathlib import Path

from backend.services import (
    nexus_peer_machine_identity_service as machine_identity,
)


def test_machine_identity_round_trip(tmp_path: Path):
    path = tmp_path / "machine.key"

    key = machine_identity.generate_private_key()

    identity = (
        machine_identity
        .public_identity_from_private_key(key)
    )

    assert identity["algorithm"] == "Ed25519"
    assert identity["fingerprint"].startswith(
        "sha256:"
    )

    machine_identity.persist_private_key(
        key,
        path=path,
    )

    assert path.exists()
    assert path.stat().st_mode & 0o777 == 0o600

    loaded_identity = (
        machine_identity.local_public_identity(
            path=path
        )
    )

    assert loaded_identity == identity

    message = b"nexus-peer-machine-auth"

    signature = machine_identity.sign(
        message,
        path=path,
    )

    assert machine_identity.verify(
        public_key=identity["publicKey"],
        message=message,
        signature=signature,
    )

    assert not machine_identity.verify(
        public_key=identity["publicKey"],
        message=b"tampered",
        signature=signature,
    )


def test_load_or_create_is_stable(tmp_path: Path):
    path = tmp_path / "machine.key"

    first = (
        machine_identity
        .load_or_create_private_key(
            path=path
        )
    )

    first_identity = (
        machine_identity
        .public_identity_from_private_key(
            first
        )
    )

    second = (
        machine_identity
        .load_or_create_private_key(
            path=path
        )
    )

    second_identity = (
        machine_identity
        .public_identity_from_private_key(
            second
        )
    )

    assert first_identity == second_identity

def test_persist_does_not_chmod_existing_custom_parent(
    tmp_path: Path,
):
    parent = tmp_path / "custom-parent"
    parent.mkdir()
    parent.chmod(0o755)

    path = parent / "machine.key"

    key = machine_identity.generate_private_key()

    machine_identity.persist_private_key(
        key,
        path=path,
    )

    assert parent.stat().st_mode & 0o777 == 0o755
    assert path.stat().st_mode & 0o777 == 0o600


def test_persist_secures_new_parent(
    tmp_path: Path,
):
    parent = tmp_path / "new-private-parent"
    path = parent / "machine.key"

    key = machine_identity.generate_private_key()

    machine_identity.persist_private_key(
        key,
        path=path,
    )

    assert parent.stat().st_mode & 0o777 == 0o700
    assert path.stat().st_mode & 0o777 == 0o600
