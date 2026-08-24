"""Operational errors for the immutable Science catalog."""


class ScienceCatalogError(RuntimeError):
    """A stored Science object is malformed, ambiguous, or cannot be resolved."""


class ScienceOperationalError(ScienceCatalogError):
    """No safe release can be selected for a verification operation."""
