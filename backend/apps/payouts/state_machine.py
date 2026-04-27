from .models import PayoutStatus, ALLOWED_TRANSITIONS


def assert_transition_legal(current_status: str, new_status: str) -> None:
    allowed = ALLOWED_TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        raise ValueError(
            f"Illegal payout state transition: '{current_status}' -> '{new_status}'. "
            f"Allowed next states from '{current_status}': {[s for s in allowed]}"
        )


def get_allowed_transitions(current_status: str) -> list:
    return ALLOWED_TRANSITIONS.get(current_status, [])
