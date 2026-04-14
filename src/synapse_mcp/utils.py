from typing import Optional


def validate_synapse_id(entity_id: str) -> bool:
    """Validate a Synapse ID format.

    Arguments:
        entity_id: The Synapse ID to validate.

    Returns:
        True if the ID matches ``syn\\d+`` format.
    """
    if not entity_id.startswith("syn"):
        return False
    return entity_id[3:].isdigit()


def mask_token(
    token: Optional[str],
) -> Optional[str]:
    """Mask a sensitive token for logging."""
    return mask_identifier(token, prefix=6)


def mask_identifier(
    value: Optional[str], *, prefix: int = 6
) -> Optional[str]:
    """Mask a sensitive identifier for logging.

    Arguments:
        value: The identifier to mask.
        prefix: Characters to leave unmasked.
    """
    if not value:
        return value
    if len(value) <= prefix:
        return value[0] + "***"
    return value[:prefix] + "***"
