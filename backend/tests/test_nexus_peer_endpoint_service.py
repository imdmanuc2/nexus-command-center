from __future__ import annotations

import pytest

from backend.services import nexus_peer_endpoint_service


def test_explicit_http_advertise_url_is_returned():
    assert (
        nexus_peer_endpoint_service
        .peer_advertise_url(
            environ={
                "NEXUS_PEER_ADVERTISE_URL":
                    "http://nexus.example:8561",
            }
        )
        == "http://nexus.example:8561"
    )


def test_explicit_https_advertise_url_is_returned():
    assert (
        nexus_peer_endpoint_service
        .peer_advertise_url(
            environ={
                "NEXUS_PEER_ADVERTISE_URL":
                    "https://nexus.example",
            }
        )
        == "https://nexus.example"
    )


def test_trailing_slash_is_normalized():
    assert (
        nexus_peer_endpoint_service
        .peer_advertise_url(
            environ={
                "NEXUS_PEER_ADVERTISE_URL":
                    "http://nexus.example:8561/",
            }
        )
        == "http://nexus.example:8561"
    )


@pytest.mark.parametrize(
    "environ",
    [
        {},
        {
            "NEXUS_PEER_ADVERTISE_URL": "",
        },
        {
            "NEXUS_PEER_ADVERTISE_URL": "   ",
        },
    ],
)
def test_missing_advertise_url_fails_closed(
    environ,
):
    with pytest.raises(
        RuntimeError,
        match="not configured",
    ):
        (
            nexus_peer_endpoint_service
            .peer_advertise_url(
                environ=environ
            )
        )


@pytest.mark.parametrize(
    "value",
    [
        "0.0.0.0:8561",
        "ftp://nexus.example:8561",
        "http://user:password@nexus.example:8561",
        "http://nexus.example:8561/api/nexus",
        "http://nexus.example:8561?x=1",
        "http://nexus.example:8561#fragment",
    ],
)
def test_invalid_advertise_url_fails_closed(
    value,
):
    with pytest.raises(
        RuntimeError,
        match="is invalid",
    ):
        (
            nexus_peer_endpoint_service
            .peer_advertise_url(
                environ={
                    "NEXUS_PEER_ADVERTISE_URL":
                        value,
                }
            )
        )


def test_listener_bind_host_is_not_used_as_fallback(
    monkeypatch,
):
    monkeypatch.setenv(
        "NEXUS_PEER_HTTP_HOST",
        "0.0.0.0",
    )

    monkeypatch.delenv(
        "NEXUS_PEER_ADVERTISE_URL",
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match="not configured",
    ):
        (
            nexus_peer_endpoint_service
            .peer_advertise_url()
        )


def test_hostname_is_not_guessed_as_fallback(
    monkeypatch,
):
    monkeypatch.setenv(
        "NEXUS_HOSTNAME",
        "some-host",
    )

    monkeypatch.delenv(
        "NEXUS_PEER_ADVERTISE_URL",
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match="not configured",
    ):
        (
            nexus_peer_endpoint_service
            .peer_advertise_url()
        )
