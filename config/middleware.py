from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class CSRFFixMiddleware(MiddlewareMixin):
    """
    Middleware to ensure CSRF cookie is set properly in all environments.
    This is especially important for Docker and production environments.
    """
    def process_request(self, request):
        # Force set CSRF cookie on all requests
        request.META["CSRF_COOKIE_USED"] = True
        
    def process_response(self, request, response):
        # Ensure CSRF cookie is set in the response
        if not request.COOKIES.get('csrftoken') and getattr(response, 'csrf_cookie_needs_reset', False):
            # Log for debugging
            logger.debug("Setting CSRF cookie explicitly via middleware")
            
            # Get the CSRF token from the request
            from django.middleware.csrf import get_token
            get_token(request)
            
        return response