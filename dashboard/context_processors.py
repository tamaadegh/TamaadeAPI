from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site

def dashboard_context(request):
    """
    Add additional context to all dashboard templates
    """
    return {
        'site_name': getattr(settings, 'SITE_NAME', 'Tamaade'),
        'site_domain': get_current_site(request).domain,
        'admin_site_header': getattr(settings, 'ADMIN_SITE_HEADER', 'Tamaade Admin'),
        'admin_site_title': getattr(settings, 'ADMIN_SITE_TITLE', 'Tamaade Admin Portal'),
        'admin_index_title': getattr(settings, 'ADMIN_INDEX_TITLE', 'Welcome to Tamaade Admin'),
    }
