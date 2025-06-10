# custom_filters.py
from datetime import datetime

def severity_color(severity):
    severity = severity.lower()
    if severity == 'critical':
        return 'danger'     # Bootstrap class → red
    elif severity == 'major':
        return 'warning'    # Bootstrap class → yellow/orange
    elif severity == 'minor':
        return 'success'    # Bootstrap class → green
    return 'secondary'      # default gray

def severity_badge(severity):
    severity = severity.lower()
    if severity == 'critical':
        return 'bg-danger'     # Bootstrap class → red
    elif severity == 'major':
        return 'bg-warning'    # Bootstrap class → yellow/orange
    elif severity == 'minor':
        return 'bg-success'    # Bootstrap class → green
    return 'bg-secondary'      # default gray

def status_badge(status):
    status = status.lower()
    if status == 'open':
        return 'bg-danger'     # Bootstrap class → red
    elif status == 'in progress':
        return 'bg-warning'    # Bootstrap class → yellow/orange
    elif status == 'closed':
        return 'bg-success'    # Bootstrap class → green
    return 'bg-secondary'      # default gray

def format_date(value):
    """Format a datetime object to a readable string."""
    if value is None:
        return ""
    return value.strftime("%B %d, %Y at %H:%M")

def nl2br(value):
    """Convert newlines to <br> tags."""
    if not value:
        return ""
    return value.replace('\n', '<br>')

def status_color(status):
    status = status.lower()
    if status == 'open':
        return 'danger'     # Bootstrap class → red
    elif status == 'in progress':
        return 'warning'    # Bootstrap class → yellow/orange
    elif status == 'closed':
        return 'success'    # Bootstrap class → green
    return 'secondary'      # default gray

def register_filters(app):
    app.jinja_env.filters['severity_color'] = severity_color
    app.jinja_env.filters['status_color'] = status_color
    app.jinja_env.filters['format_date'] = format_date
    app.jinja_env.filters['nl2br'] = nl2br
    app.jinja_env.filters['severity_badge'] = severity_badge  # Add this
    app.jinja_env.filters['status_badge'] = status_badge      # Add this
    app.jinja_env.globals['now'] = datetime.now
