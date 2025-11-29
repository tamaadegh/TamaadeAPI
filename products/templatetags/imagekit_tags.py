from django import template
from django.utils.safestring import mark_safe

register = template.Library()

try:
    from config.imagekit import imagekit
except Exception:
    imagekit = None


@register.simple_tag
def imagekit_url(src=None, width=None, height=None, quality=None, url_endpoint=None):
    """Return a transformed ImageKit URL for the given `src` or url.

    Usage in templates:
        {% load imagekit_tags %}
        {% imagekit_url image.url width=300 height=300 quality=70 as url %}
        <img src="{{ url }}" />
    """
    if not src:
        return ""
    if not imagekit:
        return src
    try:
        transformation = []
        if width:
            transformation.append({"width": str(width)})
        if height:
            transformation.append({"height": str(height)})
        if quality:
            transformation.append({"quality": str(quality)})
        data = {"src": src}
        if url_endpoint:
            data["url_endpoint"] = url_endpoint
        if transformation:
            data["transformation"] = transformation
        return imagekit.url(data)
    except Exception:
        return src
