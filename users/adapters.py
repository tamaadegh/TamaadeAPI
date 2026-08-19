"""allauth adapter that refuses to let e-mail delivery break account flows.

Signup used to return HTTP 500 for every new customer: allauth sends the
verification e-mail from inside `perform_create`, the SMTP handshake to
smtp.gmail.com failed because no credentials were configured, and the exception
propagated - *after* the user row had already been committed. Customers saw
"Server Error", then "already registered" when they retried.

Creating the account and notifying the customer are separate concerns. A
delivery failure is now recorded as an operational event that staff can see on
the dashboard, instead of being raised into the customer's request.
"""

from allauth.account.adapter import DefaultAccountAdapter

from dashboard.events import record_event
from dashboard.models import SystemEvent


class ResilientAccountAdapter(DefaultAccountAdapter):
    def send_mail(self, template_prefix, email, context):
        try:
            return super().send_mail(template_prefix, email, context)
        except Exception as exc:
            record_event(
                message="Could not send account e-mail",
                level=SystemEvent.LEVEL_ERROR,
                category=SystemEvent.CAT_EMAIL,
                detail=f"template={template_prefix}\n{type(exc).__name__}: {exc}",
                reference=email or "",
            )
            return None
