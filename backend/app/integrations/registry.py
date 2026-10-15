from dataclasses import dataclass


@dataclass(frozen=True)
class Integration:
    name: str
    base_url: str
    allowed_methods: frozenset[str]


INTEGRATIONS = {
    "local_health": Integration(
        name="local_health",
        base_url="http://127.0.0.1:47709",
        allowed_methods=frozenset({"GET"}),
    ),
}


def get_integration(name: str) -> Integration:
    """Return a registered integration or reject unknown integrations."""
    integration = INTEGRATIONS.get(name)

    if integration is None:
        raise ValueError(f"Integration '{name}' is not registered.")

    return integration


def list_integrations() -> list[dict]:
    """Return registered integrations in a JSON-friendly format."""
    return [
        {
            "name": integration.name,
            "base_url": integration.base_url,
            "allowed_methods": sorted(integration.allowed_methods),
        }
        for integration in INTEGRATIONS.values()
    ]
