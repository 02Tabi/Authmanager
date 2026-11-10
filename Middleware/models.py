from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import secrets
from django.contrib.auth.hashers import make_password, check_password

import hmac
import hashlib
from django.conf import settings


def hash_app_secret(raw_secret):
    """
    Keyed hash (HMAC-SHA256) of an application client secret.
    Includes a version marker (hmac_sha256$) to reliably identify hashed values.
    """
    key = getattr(settings, 'APP_SECRET_HMAC_KEY', settings.SECRET_KEY).encode('utf-8')
    digest = hmac.new(key, raw_secret.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"hmac_sha256${digest}"

def verify_app_secret(raw_secret, stored_value):
    """
    Verifies a provided app secret against the stored value, in constant time.
    Strictly requires the new keyed-hash format. Plaintext fallback is removed.
    """
    if not raw_secret or not stored_value:
        return False
    
    return hmac.compare_digest(hash_app_secret(raw_secret), stored_value)


def generate_app_secret():
    """Fallback default — never stores plaintext, even if a caller forgets to set app_secret explicitly."""
    raw = secrets.token_hex(32)
    return hash_app_secret(raw)

class Authenticationtype(models.Model):
    name        = models.CharField(max_length=100, unique=True) 
    description = models.TextField(blank=True, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Application(models.Model):
    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    app_name    = models.CharField(max_length=255)
    app_id      = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    app_type    = models.ForeignKey(Authenticationtype, on_delete=models.SET_NULL, null=True, blank=True, related_name='applications')  
    
   
    app_secret = models.CharField(max_length=128, unique=True, default=generate_app_secret)
    login_url  = models.URLField(max_length=500, blank=True, null=True, help_text="Where users are redirected to log in to this application.")
    
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.app_secret:
            self.app_secret = generate_app_secret()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.app_name} - {self.app_id}"

class Profile(models.Model):
    ROLE_CHOICES = [
        ('admin',   'Admin'),
        ('checker', 'Checker'),
        ('maker',   'Maker'),
        ('staff',   'Staff'),
        ('manager', 'Manager'),
        ('user',    'User'),
    ]

    STATUS_CHOICES = [
        ('active',    'Active'),
        ('inactive',  'Inactive'),
        ('suspended', 'Suspended'),
        ('banned',    'Banned'),
    ]

    AUTH_CHOICES = [
        ('AD', 'Active Directory'),
        ('DB', 'Local User'),
        ('Hybrid', 'Hybrid Access'),
    ]

    auth_type               = models.CharField(max_length=10, choices=AUTH_CHOICES, default='AD')
    is_locked               = models.BooleanField(default=False)
    requires_password_reset = models.BooleanField(default=False)
    password_last_updated   = models.DateTimeField(default=timezone.now)

    credentials_sent          = models.BooleanField(default=False)

    firstname = models.CharField(max_length=100, blank=True, null=True)
    lastname  = models.CharField(max_length=100, blank=True, null=True)
    email     = models.EmailField(unique=True, blank=True, null=True)
    phone     = models.CharField(max_length=20, blank=True, null=True)
    
    username              = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    user_role             = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')
    user_status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    failed_login_attempts = models.IntegerField(default=0)
    created_on            = models.DateTimeField(auto_now_add=True)
    created_by            = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_profiles')
    updated_on  = models.DateTimeField(auto_now=True)
    updated_by  = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="updated_user_profiles", null=True, blank=True)
    last_login  = models.DateTimeField(null=True, blank=True)
    last_logout = models.DateTimeField(null=True, blank=True)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.username.username} - Profile"

class Permission(models.Model):
    PERMISSION_CHOICES = [
        ('admin',       'Admin'),
        ('maker',       'Maker'),
        ('checker',     'Checker'),
        ('user', 'User'),
    ]

    APPROVAL_STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_permissions')
    approved_at = models.DateTimeField(null=True, blank=True)

    user            = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_permissions_custom')
    application     = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='permissions', null=True, blank=True)
    
    role            = models.CharField(max_length=50, null=True, blank=True)
    
    permission_type = models.CharField(max_length=20, choices=PERMISSION_CHOICES)
    is_active       = models.BooleanField(default=False)
    created_at      = models.DateTimeField(auto_now_add=True)

    app_password = models.CharField(max_length=128, blank=True, null=True, help_text="Isolated password hash for this specific application.")
    credentials_sent = models.BooleanField(default=False, help_text="Tracks if the SMS/Email has been sent for this specific app.")
    requires_password_reset = models.BooleanField(default=True, help_text="Forces password change on first login to this app.")

    def __str__(self):
        return f"{self.user.username} - {self.permission_type} - {self.approval_status}"

    def set_password(self, raw_password):
        self.app_password = make_password(raw_password)
        self.save(update_fields=['app_password'])

    def check_password(self, raw_password):
        return check_password(raw_password, self.app_password)

class AuthTrail(models.Model):
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed',  'Failed'),
    ]

    user       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    username   = models.CharField(max_length=150)
    app_id     = models.CharField(max_length=255, blank=True, null=True)
    status     = models.CharField(max_length=10, choices=STATUS_CHOICES)
    reason     = models.CharField(max_length=255, blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.username} - {self.status} - {self.created_at}"

class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('user_created',           'User Created'),
        ('user_deleted',           'User Deleted'),
        ('user_activated',         'User Activated'),
        ('user_deactivated',       'User Deactivated'),
        ('app_created',            'App Created'),
        ('app_deleted',            'App Deleted'),
        ('app_approved',           'App Approved'),
        ('app_rejected',           'App Rejected'),
        ('permission_granted',     'Permission Granted'),
        ('permission_revoked',     'Permission Revoked'),
        ('permission_approved',    'Permission Approved'),
        ('permission_rejected',    'Permission Rejected'),
        ('reset_attempts',         'Reset Failed Attempts'),
        ('account_locked',         'Account Locked'),
        ('password_changed',       'Password Changed'),
    ]

    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action       = models.CharField(max_length=50, choices=ACTION_CHOICES)
    target       = models.CharField(max_length=255)
    details      = models.TextField(blank=True, null=True)
    ip_address   = models.GenericIPAddressField(blank=True, null=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.performed_by} - {self.action} - {self.created_at}"

class PasswordHistory(models.Model):
    user          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_history')
    password_hash = models.CharField(max_length=255)
    created_at    = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - Password Hash created on {self.created_at}"

class OTPToken(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='otp_token')
    code = models.CharField(max_length=6)
    expires_at = models.DateTimeField()

    def is_valid(self):
        return timezone.now() <= self.expires_at

    def generate_new_code(self):
        """Generates a 6-digit code valid for 5 minutes."""
        import secrets
        import string
        self.code = ''.join(secrets.choice(string.digits) for _ in range(6))
        self.expires_at = timezone.now() + timedelta(minutes=5)
        self.save()