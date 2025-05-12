from django import template
from django.utils import timezone
from datetime import timedelta

register = template.Library()

@register.filter
def precise_timesince(value):
    """
    Returns a string representing time since the given datetime with seconds precision
    for recent times (less than a minute).
    """
    if not value:
        return ''
    
    now = timezone.now()
    diff = now - value
    
    # If less than a minute, show seconds
    if diff < timedelta(minutes=1):
        seconds = int(diff.total_seconds())
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    
    # For longer durations, use Django's built-in timesince
    from django.utils.timesince import timesince
    return timesince(value)
