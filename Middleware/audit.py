from .models import AuditLog

def log_action(performed_by, action, target, details='', ip_address=None):
    AuditLog.objects.create(
        performed_by=performed_by,
        action=action,
        target=target,
        details=details,
        ip_address=ip_address,
    )