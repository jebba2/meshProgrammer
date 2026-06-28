import pytest

from meshprogrammer import connection


def test_resolve_port_returns_explicit_port_without_scanning(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail_if_called() -> list[str]:
        raise AssertionError("should not scan when a port was given explicitly")

    monkeypatch.setattr(connection.device, "scan_ports", _fail_if_called)

    assert connection.resolve_port("COM3") == "COM3"


def test_resolve_port_auto_detects_single_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(connection.device, "scan_ports", lambda: ["COM5"])

    assert connection.resolve_port(None) == "COM5"


def test_resolve_port_raises_with_empty_ports_when_no_devices(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(connection.device, "scan_ports", lambda: [])

    with pytest.raises(connection.PortResolutionError) as exc_info:
        connection.resolve_port(None)

    assert exc_info.value.ports == []
    assert "No Meshtastic devices detected" in str(exc_info.value)


def test_resolve_port_raises_with_candidates_when_multiple_devices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(connection.device, "scan_ports", lambda: ["COM3", "COM5"])

    with pytest.raises(connection.PortResolutionError) as exc_info:
        connection.resolve_port(None)

    assert exc_info.value.ports == ["COM3", "COM5"]
    message = str(exc_info.value)
    assert "COM3" in message
    assert "COM5" in message
