"""Helper for writing SystemEvent rows.

`record_event` must never raise. It is called from inside signup, checkout and
payment-callback paths, and an observability failure must never be the reason a
customer's request breaks - that is exactly the class of bug it exists to
report.
"""

import logging

logger = logging.getLogger(__name__)


def record_event(
    message,
    level=None,
    category=None,
    detail="",
    reference="",
    user=None,
):
    """Write one operational event. Swallows all errors by design."""
    try:
        from dashboard.models import SystemEvent

        # Anonymous/unauthenticated users must not be passed through as a FK.
        if user is not None and not getattr(user, "is_authenticated", False):
            user = None

        return SystemEvent.objects.create(
            level=level or SystemEvent.LEVEL_INFO,
            category=category or SystemEvent.CAT_OTHER,
            message=str(message)[:300],
            detail="" if detail is None else str(detail)[:5000],
            reference=str(reference or "")[:120],
            user=user,
        )
    except Exception:
        # Last resort: keep it in the container log and carry on.
        logger.warning("record_event failed for message=%r", message, exc_info=True)
        return None
