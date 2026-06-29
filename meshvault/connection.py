"""Device-connection resolution shared by the CLI and the web GUI.

Both surfaces need to auto-detect which serial port to use when the caller
didn't name one explicitly; only how they report failure differs (a printed
message for the CLI, a JSON error for the GUI), so that reporting is left to
each caller via ``PortResolutionError.ports``.
"""

from meshvault import device


class PortResolutionError(Exception):
    """Raised when ``resolve_port`` can't auto-detect a single port.

    ``ports`` holds what ``device.scan_ports()`` found: empty if none were
    connected, or more than one if the choice is ambiguous.
    """

    def __init__(self, ports: list[str]) -> None:
        self.ports = ports
        message = (
            "No Meshtastic devices detected."
            if not ports
            else f"Multiple devices detected ({', '.join(ports)})."
        )
        super().__init__(message)


def resolve_port(port: str | None) -> str:
    """Return ``port`` unchanged, or auto-detect it if not given explicitly.

    Auto-detection only succeeds when exactly one Meshtastic device is
    connected. Raises ``PortResolutionError`` if there's none or more than
    one and the caller didn't say which to use.
    """
    if port is not None:
        return port
    ports = device.scan_ports()
    if len(ports) == 1:
        return ports[0]
    raise PortResolutionError(ports)
