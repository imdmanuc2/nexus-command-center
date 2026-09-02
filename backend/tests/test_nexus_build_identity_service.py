from backend.services import nexus_build_identity_service


def test_build_identity_uses_runtime_metadata(monkeypatch):
    monkeypatch.setenv("NEXUS_VERSION", "1.2.3")
    monkeypatch.setenv(
        "NEXUS_REVISION",
        "0123456789abcdef0123456789abcdef01234567",
    )

    assert nexus_build_identity_service.build_identity() == {
        "version": "1.2.3",
        "revision": "0123456789abcdef0123456789abcdef01234567",
    }


def test_build_identity_defaults_when_metadata_missing(monkeypatch):
    monkeypatch.delenv("NEXUS_VERSION", raising=False)
    monkeypatch.delenv("NEXUS_REVISION", raising=False)

    assert nexus_build_identity_service.build_identity() == {
        "version": "development",
        "revision": "unknown",
    }


def test_build_identity_defaults_for_blank_metadata(monkeypatch):
    monkeypatch.setenv("NEXUS_VERSION", "   ")
    monkeypatch.setenv("NEXUS_REVISION", "")

    assert nexus_build_identity_service.build_identity() == {
        "version": "development",
        "revision": "unknown",
    }
