from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from cryptography.hazmat.primitives.asymmetric import padding
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone 
from django.db.models import F
from datetime import timedelta
from Middleware.tasks import send_otp_async
from django.contrib import messages
from django.db.models import Count
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
from .serializers import LoginSerializer
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .libs.ad import authenticate_user
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User
from .models import Application, Permission, Authenticationtype, Profile, AuthTrail, AuditLog
from .models import PasswordHistory
from django.conf import settings
import string 
# import random
import secrets
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from django.views.decorators.cache import never_cache
from django.core.paginator import Paginator
from functools import wraps
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
import uuid
from django.core.cache import cache
from rest_framework.throttling import SimpleRateThrottle

import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from django.http import JsonResponse
from rest_framework import status
import os
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.urls import reverse
from django.http import HttpResponseBadRequest
from django.http import HttpResponseForbidden
from .decorators import admin_required
from .decorators import auth_manager_access_required
from .models import hash_app_secret, verify_app_secret
from django.core import signing
from .notifications import sms_helper, mail_helper 



def dispatch_otp(user):
    otp_record, created = OTPToken.objects.get_or_create(user=user)
    otp_record.generate_new_code()
    
    profile = getattr(user, 'profile', None)
    message = (
        f"Your Prudential Bank Auth Manager login code is: {otp_record.code}. "
        f"It expires in 5 minutes. Do not share this code with anyone."
    )
    
    try:
        sms_helper(profile.phone if profile else None, message)
        mail_helper(profile.email if profile else None, message)
    except Exception:
        pass 

def decrypt_payload(encrypted_password_base64: str) -> str:
    """Decrypts a Base64 encoded RSA-OAEP string back to plain text."""
    try:
        raw_key = os.environ.get('PRIVATE_KEY_PEM', '').replace('\\n', '\n').strip('"').strip("'")
        private_key_bytes = raw_key.encode('utf-8')

        private_key = serialization.load_pem_private_key(
            private_key_bytes,
            password=None,
        )
        encrypted_bytes = base64.b64decode(encrypted_password_base64)
        decrypted_bytes = private_key.decrypt(
            encrypted_bytes,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return decrypted_bytes.decode('utf-8')

    except Exception as e:
        return None

class LoginBruteForceThrottle(SimpleRateThrottle):
    scope = 'api_brute_force'
    
    def get_cache_key(self, request, view):
        username = request.data.get('username')
        app_id = request.data.get('app_id', 'unknown_app')
        
        if username:
            return self.cache_format % {
                'scope': self.scope,
                'ident': f"{app_id}_{username}"
            }
            
        return self.cache_format % {
            'scope': self.scope,
            'ident': get_client_ip(request)
        }


class LoginIPThrottle(SimpleRateThrottle):
    """
    Layers a source-IP throttle on top of the account-based throttle above,
    so a single IP cannot spray attempts across many different usernames
    to bypass the per-account limit.
    """
    scope = 'api_ip_brute_force'

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': get_client_ip(request)
        }


  
def get_client_ip(request):
    """
    Securely gets the client IP. 
    Only trusts X-Forwarded-For if the request comes from a trusted proxy.
    """
    remote_addr = request.META.get('REMOTE_ADDR', '')
    
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

    if x_forwarded_for:
        if remote_addr in settings.TRUSTED_PROXIES:
            return x_forwarded_for.split(',')[0].strip()
        else:
            
            return remote_addr.strip()
            
    return remote_addr.strip()

def is_rate_limited(cache_key, limit, window_seconds):
    """Simple fixed-window rate limiter using Django's existing cache backend."""
    count = cache.get(cache_key)
    if count is None:
        cache.set(cache_key, 1, timeout=window_seconds)
        return False
    if count >= limit:
        return True
    cache.incr(cache_key)
    return False    


def log_action(performed_by, action, target='', details='', ip_address=''):
    AuditLog.objects.create(
        performed_by=performed_by,
        action=action,
        target=target,
        details=details,
        ip_address=ip_address
    )


def get_user_permission_types(user):
    return set(
        Permission.objects.filter(
            user=user, is_active=True, approval_status='approved'
        ).values_list('permission_type', flat=True)
    )

APPROVER_ROLES = {'admin', 'checker'}

ROLE_HIERARCHY = {
    'admin': 3,
    'checker': 2,
    'maker': 1,
}

def get_role_weight(role_name):
    """
    Canonical role-weight lookup. 
    Fails closed: unknown, blank, or profile-based roles get weight 0.
    """
    if not role_name:
        return 0
    return ROLE_HIERARCHY.get(role_name.strip().lower().replace(' ', '_'), 0)

def has_auth_manager_permission(user, min_weight=1):
    """
    Single canonical authorization check: requires an approved, active
    AUTH_MANAGER permission whose role meets min_weight, or superuser.
    Replaces scattered/inconsistent Profile.user_role vs Permission.permission_type checks.
    """
    if user.is_superuser:
        return True
    perm = Permission.objects.filter(
        user=user,
        application__app_id='AUTH_MANAGER',
        is_active=True,
        approval_status='approved'
    ).first()
    if not perm:
        return False
    return get_role_weight(perm.permission_type) >= min_weight

def can_approve(user):
    return bool(get_user_permission_types(user) & APPROVER_ROLES)

def check_privilege_escalation(request_user, target_roles):
    """Returns (True, role_name) if attempting to grant unauthorized privileges."""
    request_weight = 0
    is_admin = request_user.is_superuser

    auth_perm = Permission.objects.filter(
        user=request_user,
        application__app_id='AUTH_MANAGER',
        is_active=True,
        approval_status='approved'
    ).first()

    if auth_perm:
        perm_type = auth_perm.permission_type.strip().lower()
        request_weight = get_role_weight(perm_type)
        if perm_type == 'admin':
            is_admin = True

    if is_admin:
        request_weight = max(request_weight, 3)

    for role in target_roles:
        clean_role = role.strip() if role else ""
        target_weight = get_role_weight(clean_role)

        if request_weight >= 3:
            continue

        if target_weight > request_weight:
            return True, role

    return False, None

@method_decorator(csrf_exempt, name='dispatch')
class LoginView(APIView):
    throttle_classes = [LoginBruteForceThrottle, LoginIPThrottle]
    
    def post(self, request):
        app_id = request.data.get('app_id')
        provided_secret = request.headers.get('X-App-Secret')
        client_ip = get_client_ip(request)

        if not provided_secret:
            AuditLog.objects.create(
                action='api_security_breach',
                target=app_id or 'Unknown App',
                details='Blocked API request: Missing X-App-Secret header.',
                ip_address=client_ip
            )
            return JsonResponse(
                {'message': 'Access Denied: Missing X-App-Secret header.'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            application = Application.objects.get(app_id=app_id, status='approved')
            if not verify_app_secret(provided_secret, application.app_secret):
                AuditLog.objects.create(
                    action='api_security_breach',
                    target=app_id,
                    details='Blocked API request: Invalid X-App-Secret provided.',
                    ip_address=client_ip
                )
                return JsonResponse(
                    {'message': 'Access Denied: Invalid App Secret.'}, 
                    status=status.HTTP_403_FORBIDDEN
                )

            if application.app_secret != hash_app_secret(provided_secret):
                application.app_secret = hash_app_secret(provided_secret)
                application.save(update_fields=['app_secret'])
        except Application.DoesNotExist:
            AuditLog.objects.create(
                action='api_security_breach',
                target=str(app_id),
                details='Blocked API request: Unregistered or inactive Application.',
                ip_address=client_ip
            )
            return JsonResponse(
                {'message': 'Access Denied: Unregistered or inactive Application.'}, 
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = LoginSerializer(data=request.data)
        
        if not serializer.is_valid():
            errors = dict(serializer.errors)
            if 'permission_type' in errors:
                del errors['permission_type'] 
            if errors: 
                return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        username = request.data.get('username')
        encrypted_password = request.data.get('password') 
        app_id   = request.data.get('app_id')
        requested_permission = request.data.get('permission_type') 

        generic_error = JsonResponse(
            {'message': 'Authentication failed: Invalid username, password, or access denied.'}, 
            status=status.HTTP_401_UNAUTHORIZED
        )

        password = decrypt_payload(encrypted_password)

        if not password:
            AuditLog.objects.create(
                action='api_security_breach',
                target=username or 'Unknown',
                details='Blocked API request: Payload decryption failed. Possible tampering or plain-text sent.',
                ip_address=client_ip
            )
            return generic_error

        try:
            user = User.objects.get(username=username)
            profile = getattr(user, 'profile', None)
        except User.DoesNotExist:
            user = None
            profile = None

        if not user or not profile:
            return generic_error

        if profile.is_locked:
            return generic_error

        if cache.get(f"account_lockout_{username}"):
            return generic_error

        if profile.last_login and (timezone.now() - profile.last_login).days >= 90:
            profile.is_active = False
            profile.user_status = 'inactive'
            profile.save(update_fields=['is_active', 'user_status'])
            return generic_error 
            
        is_dashboard_login = not app_id or app_id == "AUTH_MANAGER"

        if is_dashboard_login:
            if profile.auth_type != 'AD':
                return JsonResponse(
                    {'message': 'Access Denied: Only Active Directory accounts are permitted on this portal.'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
            permission_record = Permission.objects.filter(
                user=user,
                application__app_id='AUTH_MANAGER',
                is_active=True,
                approval_status='approved'
            ).first()
        else:
            try:
                application = Application.objects.get(app_id=app_id, status='approved')
                
                permission_record = Permission.objects.filter(
                    user=user, 
                    application=application, 
                    is_active=True,
                    approval_status='approved' 
                ).first()
            except Application.DoesNotExist:
                permission_record = None

        if not permission_record:
            return generic_error

        if requested_permission and permission_record.permission_type != requested_permission:
            AuditLog.objects.create(
                action='api_security_breach',
                target=username,
                details=f'Blocked login: Requested {requested_permission} but assigned {permission_record.permission_type}',
                ip_address=client_ip
            )
            return JsonResponse(
                {'message': 'Authentication failed: Invalid permission type.'}, 
                status=status.HTTP_403_FORBIDDEN
            )

        is_local_app = False
        if not is_dashboard_login and permission_record.application and permission_record.application.app_type:
            app_type_name = permission_record.application.app_type.name.upper()
            if 'DB' in app_type_name or 'LOCAL' in app_type_name:
                is_local_app = True

        is_authenticated = False
        
        try:
            is_authenticated = authenticate_user(username, password)
        except Exception:
            is_authenticated = False
            
        if not is_authenticated:
            is_authenticated = user.check_password(password)
            
            if not is_authenticated and hasattr(permission_record, 'check_password'):
                is_authenticated = permission_record.check_password(password)

        if is_authenticated:
            if not user.is_active or not profile.is_active:
                AuditLog.objects.create(
                    action='api_login_blocked',
                    target=username,
                    details='API login denied: Account deactivated or pending approval',
                    ip_address=get_client_ip(request)
                )
                return generic_error

         
            profile.failed_login_attempts = 0
            profile.save(update_fields=['failed_login_attempts'])

            
            otp_code = ''.join(secrets.choice(string.digits) for _ in range(6))
            temp_token = str(uuid.uuid4())
            
            cache_data = {
                'user_id': user.id,
                'permission_type': permission_record.permission_type,
                'role': permission_record.role,
                'is_local_app': is_local_app,
                'requires_password_reset': getattr(permission_record, 'requires_password_reset', False),
                'username': username
            }
            
            cache.set(f"api_otp_data_{temp_token}", cache_data, timeout=300)
            cache.set(f"api_otp_code_{temp_token}", otp_code, timeout=300)
            
            
            otp_message = (
                f"Dear {profile.firstname or user.username},\n\n"
                f"Your Auth Manager API login code is: {otp_code}\n\n"
                f"This code will expire in 5 minutes."
            )
            
            try:
                send_otp_async.delay(profile.phone, otp_message)
            except Exception as e:
                pass
                
            return JsonResponse({
                'message': 'Password verified. Two-Factor Authentication required.',
                'status': 'otp_required',
                'temp_token': temp_token,
                'expires_in': 300
            }, status=status.HTTP_202_ACCEPTED)
            
        else:
            profile.__class__.objects.filter(pk=profile.pk).update(
                failed_login_attempts=F('failed_login_attempts') + 1
            )
            
            profile.refresh_from_db(fields=['failed_login_attempts'])

            if profile.failed_login_attempts >= 3:
                backoff_seconds = min(60 * (2 ** (profile.failed_login_attempts - 3)), 3600)
                cache.set(f"account_lockout_{username}", True, timeout=backoff_seconds)

                AuditLog.objects.create(
                    action='account_locked',
                    target=username,
                    details=f'Temporarily locked for {backoff_seconds}s after {profile.failed_login_attempts} failed attempts (exponential backoff)',
                    ip_address=get_client_ip(request)
                )
            
            return generic_error

def portal_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        ip    = get_client_ip(request)
        agent = request.META.get('HTTP_USER_AGENT', '')[:255]

        if is_rate_limited(f"portal_login_ip_{ip}", limit=10, window_seconds=60):
            error = 'Too many login attempts from this location. Please wait a moment and try again.'
            return render(request, 'pages/login.html', {'error': error})

        if username and cache.get(f"account_lockout_{username}"):
            error = 'This account is temporarily locked due to multiple failed login attempts. Please try again later.'
            return render(request, 'pages/login.html', {'error': error})

        user  = User.objects.filter(username=username).first()

        is_authenticated = False
        profile = None

        if user:
            profile = getattr(user, 'profile', None)
            if profile:
                if profile.auth_type == 'AD':
                    is_authenticated = authenticate_user(username, password)
                elif profile.auth_type == 'DB':
                    is_authenticated = user.check_password(password)

        if is_authenticated:
            if profile.auth_type == 'DB':
                AuthTrail.objects.create(
                    user=user, username=username, status='failed',
                    reason='Portal access denied for Local DB user', ip_address=ip, user_agent=agent
                )
                error = 'Access Denied. Local users must log in directly through their assigned applications.'
                
            elif not user.is_active or not profile.is_active:
                AuthTrail.objects.create(
                    user=user, username=username, status='failed',
                    reason='Account inactive or pending approval', ip_address=ip, user_agent=agent
                )
                error = 'Your account has been deactivated or is pending approval. Please contact a System Administrator.'
            
            else:
                has_iam_access = Permission.objects.filter(
                    user=user,
                    application__app_id='AUTH_MANAGER',
                    permission_type__in=['admin', 'maker', 'checker'],
                    is_active=True,
                    approval_status='approved'
                ).exists()

                if not has_iam_access:
                    AuthTrail.objects.create(
                        user=user, username=username, status='failed',
                        reason='Portal access denied: Not an IAM Administrator', ip_address=ip, user_agent=agent
                    )
                    error = 'Access Denied: Only authorized IAM Administrators can log into the Auth Manager.'
                
                else:
                    
                    otp_code = ''.join(secrets.choice(string.digits) for _ in range(6))
                    
                    cache.set(f"otp_auth_{user.id}", otp_code, timeout=300)
                    
                    request.session['pre_2fa_user_id'] = user.id
                    
                    otp_message = (
                        f"Dear {profile.firstname or user.username},\n\n"
                        f"Your Auth Manager login code is: {otp_code}\n\n"
                        f"This code will expire in 5 minutes. Do not share this with anyone."
                    )
                    
                    try:
                        send_otp_async.delay(profile.phone, otp_message)
                    except Exception:
                        pass
                        
                    return redirect('portal_otp_verify')
                   
        else:
            AuthTrail.objects.create(
                user=user, username=username, status='failed',
                reason='Invalid username or password', ip_address=ip, user_agent=agent,
            )
            if profile:
                profile.failed_login_attempts += 1
                profile.save()

                if profile.failed_login_attempts >= 3:
                    backoff_seconds = min(60 * (2 ** (profile.failed_login_attempts - 3)), 3600)
                    cache.set(f"account_lockout_{username}", True, timeout=backoff_seconds)
                    log_action(None, 'account_locked', username,
                               f'Temporarily locked for {backoff_seconds}s after {profile.failed_login_attempts} failed attempts (portal login)',
                               ip)
            error = 'Invalid username or password.'

    return render(request, 'pages/login.html', {'error': error})

def portal_logout(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('portal_login')


@never_cache 
@login_required(login_url='portal_login')
def dashboard(request):
    now   = timezone.now()
    today = now.date()
    this_week_start = today - timedelta(days=today.weekday())
    last_week_start = this_week_start - timedelta(days=7)

    total_users        = Profile.objects.count()
    total_apps         = Application.objects.count()
    active_permissions = Permission.objects.filter(is_active=True).count()
    pending_approvals  = Permission.objects.filter(approval_status='pending').count()

    months, logins_per_month, active_users_per_month, new_users_per_month = [], [], [], []
    for i in range(6, -1, -1):
        month_start = (now.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
        month_end   = (month_start + timedelta(days=32)).replace(day=1)
        months.append(month_start.strftime('%b'))
        logins_per_month.append(Profile.objects.filter(last_login__gte=month_start, last_login__lt=month_end).count())
        active_users_per_month.append(Permission.objects.filter(is_active=True, created_at__gte=month_start, created_at__lt=month_end).count())
        new_users_per_month.append(Profile.objects.filter(created_at__gte=month_start, created_at__lt=month_end).count())

    total_logins  = Profile.objects.exclude(last_login=None).count()
    active_users  = Profile.objects.filter(is_active=True).count()
    inactive_users = Profile.objects.filter(is_active=False).count()
    approved_apps = Application.objects.filter(status='approved').count()
    rejected_apps = Application.objects.filter(status='rejected').count()

    weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    progress_group_weekdays = []
    for i, day in enumerate(weekdays):
        this_day   = this_week_start + timedelta(days=i)
        last_day   = last_week_start + timedelta(days=i)
        this_count = Profile.objects.filter(last_login__date=this_day).count()
        last_count = Profile.objects.filter(last_login__date=last_day).count()
        max_val    = max(this_count, last_count, 1)
        progress_group_weekdays.append({
            'title': day[:3],
            'value1': round((this_count / max_val) * 100),
            'value2': round((last_count / max_val) * 100),
        })

    role_counts    = Profile.objects.values('user_role').annotate(count=Count('id'))
    total_profiles = Profile.objects.count() or 1
    progress_group_roles = [
        {'title': r['user_role'].replace('_', ' ').title(), 'value': round((r['count'] / total_profiles) * 100)}
        for r in role_counts
    ]

    app_type_counts  = Application.objects.values('app_type__name').annotate(count=Count('id'))
    total_apps_count = Application.objects.count() or 1
    progress_group_apps = [
        {'title': a['app_type__name'] or 'Unknown', 'value': a['count'],
         'percent': round((a['count'] / total_apps_count) * 100), 'icon': 'cil-puzzle'}
        for a in app_type_counts
    ]

    recent_permissions = Permission.objects.select_related('user', 'user__profile', 'application').order_by('-created_at')[:10]
    table_rows = []
    for perm in recent_permissions:
        profile = getattr(perm.user, 'profile', None)
        table_rows.append({
            'user':        perm.user.username,
            'fullname':    f"{profile.firstname or ''} {profile.lastname or ''}".strip() if profile else '—',
            'role':        profile.user_role if profile else '—',
            'application': perm.application.app_name if perm.application else '—',
            'permission':  perm.permission_type,
            'status':      perm.is_active,
            'last_login':  profile.last_login if profile else None,
            'created_at':  perm.created_at,
        })

    return render(request, 'dashboard/dashboard.html', {
        'total_users': total_users, 'total_apps': total_apps,
        'active_permissions': active_permissions, 'pending_approvals': pending_approvals,
        'months': months, 'logins_per_month': logins_per_month,
        'active_users_per_month': active_users_per_month, 'new_users_per_month': new_users_per_month,
        'total_logins': total_logins, 'active_users': active_users, 'inactive_users': inactive_users,
        'approved_apps': approved_apps, 'rejected_apps': rejected_apps,
        'progress_group_weekdays': progress_group_weekdays,
        'progress_group_roles': progress_group_roles,
        'progress_group_apps': progress_group_apps,
        'table_rows': table_rows,
    })


@never_cache 
@login_required(login_url='portal_login')
@auth_manager_access_required
def user_management(request):
    profiles = list(Profile.objects.select_related('username').order_by('-created_at'))
    permissions = Permission.objects.select_related('user', 'user__profile', 'application').all()
    applications = Application.objects.all()

    
    is_admin = has_auth_manager_permission(request.user, 3)
    is_checker = has_auth_manager_permission(request.user, 2) and not is_admin
    is_maker = has_auth_manager_permission(request.user, 1) and not is_admin and not is_checker
    is_checker_db = is_checker

    if is_admin:
        ui_can_add_user = True
        ui_can_approve = False
        ui_is_checker = False
    elif is_maker:
        ui_can_add_user = True
        ui_can_approve = False
        ui_is_checker = False
    elif is_checker_db:
        ui_can_add_user = False
        ui_can_approve = True
        ui_is_checker = True
    else:
        ui_can_add_user = False
        ui_can_approve = False
        ui_is_checker = False

    user_stats = {}
    for perm in permissions:
        uid = perm.user_id
        if uid not in user_stats:
            user_stats[uid] = {'total': 0, 'approved': 0, 'pending': 0, 'rejected': 0}
            
        user_stats[uid]['total'] += 1
        
        if perm.approval_status == 'approved':
            user_stats[uid]['approved'] += 1
        elif perm.approval_status == 'pending':
            user_stats[uid]['pending'] += 1
        elif perm.approval_status == 'rejected':
            user_stats[uid]['rejected'] += 1

    for profile in profiles:
        uid = profile.username_id
        stats = user_stats.get(uid, {'total': 0, 'approved': 0, 'pending': 0, 'rejected': 0})
        profile.app_count = stats['total']
        profile.approved_count = stats['approved']
        profile.pending_count = stats['pending']
        profile.rejected_count = stats['rejected']

    return render(request, 'base/tables.html', {
        'profiles': profiles,
        'permissions': permissions,
        'applications': applications,
        'can_approve': ui_can_approve,
        'is_checker': ui_is_checker,
        'can_add_user': ui_can_add_user,
    })


@never_cache 
@login_required(login_url='portal_login')
def add_user(request):
 
    if has_auth_manager_permission(request.user, 2) and not has_auth_manager_permission(request.user, 3):
        log_action(request.user, 'access_denied', request.path, 'Attempted to reach user-creation controls', get_client_ip(request))
        messages.error(request, 'Access Denied: Checkers are not authorized to profile new accounts. They can only approve.')
        return redirect('user_management')
    
    if request.method == 'POST':
        username        = request.POST.get('username')
        firstname       = request.POST.get('firstname', '').strip()
        lastname        = request.POST.get('lastname', '').strip()
        email           = request.POST.get('email', '').strip()
        phone           = request.POST.get('phone', '').strip()
        auth_type       = request.POST.get('auth_type', 'AD')
        ip              = get_client_ip(request)

        if not email or not phone or not username:
            messages.error(request, "Username, Email, and Phone are mandatory fields.")
            return redirect('user_management')

        user_roles = request.POST.getlist('user_role[]')
        app_ids    = request.POST.getlist('app_id[]')
        perm_types = request.POST.getlist('permission_type[]')

        if user_roles:
            escalation_attempt, target_role = check_privilege_escalation(request.user, user_roles)
            if escalation_attempt:
                log_action(request.user, 'privilege_escalation_blocked', request.path, f'Attempted to grant equal or higher role: {target_role}', get_client_ip(request))
                messages.error(request, "Access Denied: You cannot grant privileges equal to or higher than your own.")
                return redirect('user_management')

        if user_roles or app_ids or perm_types:
            if not (len(user_roles) == len(app_ids) == len(perm_types)):
                messages.error(request, "Incomplete access row detected. Please check your form data.")
                return redirect('user_management')
            
            for r, a, p in zip(user_roles, app_ids, perm_types):
                if not r.strip() or not a.strip() or not p.strip():
                    messages.error(request, "You cannot save incomplete access rows. Role, Application, and Permission must all be selected.")
                    return redirect('user_management')

        primary_role = user_roles[0] if user_roles else 'staff'

        user, created = User.objects.get_or_create(username=username)
        if created:
            user.first_name = firstname
            user.last_name  = lastname
            user.email      = email
            user.save() 

        profile, _ = Profile.objects.get_or_create(username=user)
        profile.firstname = firstname
        profile.lastname  = lastname
        profile.email     = email
        profile.phone     = phone
        profile.user_role = primary_role
        profile.auth_type = auth_type 
        
        if created:
            user.is_active = False
            user.save()
            profile.is_active = False 
            
            if auth_type == 'DB':
                profile.requires_password_reset = True
            
        profile.save()

        for role_val, app_id, perm_type in zip(user_roles, app_ids, perm_types):
            application = Application.objects.filter(id=int(app_id)).first()
            if application:
                Permission.objects.get_or_create(
                    user=user,
                    application=application,
                    permission_type=perm_type,
                    defaults={
                        'role': role_val,
                        'is_active': False, 
                        'approval_status': 'pending'
                    }
                )
                log_action(
                    performed_by=request.user, action='permission_granted',
                    target=username,
                    details=f'{perm_type} access requested for {application.app_name}',
                    ip_address=ip
                )

        log_action(performed_by=request.user, action='user_created', target=username, details=f'User created ({auth_type})', ip_address=ip)
        messages.success(request, f"User '{username}' successfully profiled and is pending activation and approval!")
        return redirect('user_management')

    applications = Application.objects.all()
    return render(request, 'base/add_user.html', {'applications': applications})

def admin_required(min_weight=3, target_app='AUTH_MANAGER'):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('portal_login')
            
            profile = getattr(request.user, 'profile', None)
            current_role = profile.user_role.strip().lower() if profile and profile.user_role else ""
            weight = get_role_weight(current_role)

            is_superuser = request.user.is_superuser
            
            has_admin_permission = Permission.objects.filter(
                user=request.user, 
                permission_type='admin', 
                application__app_id=target_app, # <-- The required target lock
                is_active=True
            ).exists()
            
            if is_superuser or current_role == 'admin' or has_admin_permission:
                weight = max(weight, 3)

            if weight < min_weight:
                messages.error(request, "Access Denied: Insufficient administrative privileges.")
                return redirect('dashboard')
                
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
 

@login_required(login_url='portal_login')
@require_POST  
def toggle_user_status(request, perm_id, activate):
    if not has_auth_manager_permission(request.user, 3):
        log_action(request.user, 'access_denied', f'Permission {perm_id}', 'Maker/Checker attempted to toggle permission status', get_client_ip(request))
        messages.error(request, 'Access Denied: Only Admins and Super Admins can toggle live permissions.')
        return redirect('user_management')

    perm = get_object_or_404(Permission, id=perm_id)
    is_activating = bool(int(activate))
    
    if perm.is_active == is_activating:
        status_name = "active" if is_activating else "inactive"
        messages.info(request, f"User's permission is already {status_name}.")
        return redirect('user_management')

    perm.is_active = is_activating
    perm.save()
    
    if is_activating:
        messages.success(request, f"Permission activated for {perm.user.username}.")
    else:
        messages.warning(request, f"Permission deactivated for {perm.user.username}.")
        
    return redirect('user_management')
 

@login_required(login_url='portal_login')
@require_POST
def approve_permission(request, perm_id):
    if has_auth_manager_permission(request.user, 3):
        messages.error(request, "Admins are strictly forbidden from approving requests.")
        return redirect('user_management')

    if not can_approve(request.user):
        messages.error(request, "Only authorized Checkers can approve requests.")
        return redirect('user_management')

    perm = get_object_or_404(Permission, id=perm_id)

    if perm.user == request.user:
        messages.error(request, "Maker-Checker Enforced: You cannot approve a request you initiated.")
        return redirect('user_management')

    perm.approval_status = 'approved'
    perm.is_active       = True
    perm.approved_by     = request.user
    perm.approved_at     = timezone.now()
    perm.save()

    if perm.application and perm.application.app_type:
        app_type_name = perm.application.app_type.name.upper()
        is_local_app = 'DB' in app_type_name or 'LOCAL' in app_type_name

        if is_local_app:
            user = perm.user
            profile = user.profile

            user.set_unusable_password()
            user.save()

            if profile.auth_type == 'AD':
                profile.auth_type = 'Hybrid'
            elif not profile.auth_type:
                profile.auth_type = 'DB'

            profile.requires_password_reset = True
            profile.save(update_fields=['requires_password_reset', 'auth_type'])

            token = signing.dumps(
                {"perm_id": perm.id, "username": user.username},
                salt='app-credential-activation'
            )
            
            app_login_url = perm.application.login_url if perm.application and perm.application.login_url else None
            
            if app_login_url:
                clean_url = app_login_url.rstrip('/')
                activation_link = f"{clean_url}?activation_token={token}"
            else:
                activation_link = request.build_absolute_uri(
                    reverse('activate_app_credentials', args=[token])
                )

            notify_message = (
                f"Dear {profile.firstname or user.username},\n\n"
                f"You have been granted access to {perm.application.app_name}. "
                f"Use the link below to activate your login. This link is single-use "
                f"and expires in 10 minutes:\n\n"
                f"{activation_link}\n\n"
                f"NOTE: This does not affect your existing login for any other application.\n\n"
                f"Thank you,\nPrudential Bank Ltd."
            )

            try:
                sms_helper(profile.phone, notify_message)
                mail_helper(profile.email, notify_message)
            except Exception:
                messages.warning(request, "App approved, but the activation notification failed to send.")

    log_action(
        performed_by=request.user, action='permission_approved',
        target=perm.user.username,
        details=f'{perm.permission_type} permission approved for {perm.application.app_name}',
        ip_address=get_client_ip(request)
    )

    messages.success(request, f"Permission successfully approved for {perm.user.username}.")
    return redirect('user_management')


@login_required(login_url='portal_login')
@require_POST
def reject_permission(request, perm_id):
    if has_auth_manager_permission(request.user, 3):
        messages.error(request, "Admins are strictly forbidden from rejecting requests.")
        return redirect('user_management')

    if not can_approve(request.user):
        messages.error(request, "Only authorized Checkers can reject permissions.")
        return redirect('user_management')

    perm = get_object_or_404(Permission, id=perm_id)

    if perm.user == request.user:
        messages.error(request, "Maker-Checker Enforced: You cannot reject a request you initiated.")
        return redirect('user_management')

    perm.approval_status = 'rejected'
    perm.is_active       = False
    perm.approved_by     = request.user
    perm.approved_at     = timezone.now()
    perm.save()

    log_action(
        performed_by=request.user, action='permission_rejected',
        target=perm.user.username,
        details=f'{perm.permission_type} permission rejected for {perm.application.app_name}',
        ip_address=get_client_ip(request)
    )
    
    messages.warning(request, f"Permission request rejected for {perm.user.username}.")
    return redirect('user_management')


@never_cache 
@login_required(login_url='portal_login')
def edit_user(request, profile_id):
    
    if has_auth_manager_permission(request.user, 2) and not has_auth_manager_permission(request.user, 3): 
        log_action(request.user, 'access_denied', request.path, f'Checker attempted to edit user profile {profile_id}', get_client_ip(request))
        messages.error(request, 'Access Denied: Checkers can only approve/reject records, they cannot edit them.')
        return redirect('user_management')

    profile = get_object_or_404(Profile, id=profile_id)
        
    if request.method == 'POST':
        new_username = request.POST.get('username', '').strip()
        new_email    = request.POST.get('email', '').strip()
        new_phone    = request.POST.get('phone', '').strip()
        firstname    = request.POST.get('firstname', '').strip()
        lastname     = request.POST.get('lastname', '').strip()
        
        new_auth_type = request.POST.get('auth_type', profile.auth_type)

        if not new_email or not new_phone:
            messages.error(request, "Email and Phone are mandatory fields.")
            return redirect('user_management')

        user_roles = request.POST.getlist('user_role[]')
        app_ids    = request.POST.getlist('app_id[]')
        perm_types = request.POST.getlist('permission_type[]')
    
        if user_roles:
            escalation_attempt, target_role = check_privilege_escalation(request.user, user_roles)
            
            if escalation_attempt:
                if hasattr(profile.username, 'id') and request.user.id == profile.username.id:
                    escalation_attempt = False 

            if escalation_attempt:
                log_action(request.user, 'privilege_escalation_blocked', request.path, f'Attempted to grant equal or higher role: {target_role}', get_client_ip(request))
                messages.error(request, "Access Denied: You cannot grant privileges equal to or higher than your own.")
                return redirect('user_management')

        if user_roles or app_ids or perm_types:
            if not (len(user_roles) == len(app_ids) == len(perm_types)):
                messages.error(request, "Incomplete access row detected. Please check your form data.")
                return redirect('user_management')
            
            for r, a, p in zip(user_roles, app_ids, perm_types):
                if not r.strip() or not a.strip() or not p.strip():
                    messages.error(request, "You cannot save incomplete access rows. Role, Application, and Permission must all be selected.")
                    return redirect('user_management')

        if new_username and new_username != profile.username.username:
            if not User.objects.filter(username=new_username).exists():
                user = profile.username
                user.username = new_username
                user.save()
            else:
                messages.error(request, f"Username '{new_username}' is already taken.")
                return redirect('user_management')

        if not Profile.objects.exclude(id=profile.id).filter(email=new_email).exists():
            profile.email = new_email
        else:
            messages.error(request, f"Email '{new_email}' is already in use.")
            return redirect('user_management')

        if profile.auth_type == 'AD' and new_auth_type == 'DB':
            final_auth_type = 'Hybrid'
        else:
            final_auth_type = new_auth_type

        profile.firstname = firstname
        profile.lastname  = lastname
        profile.phone     = new_phone
        profile.auth_type = final_auth_type 

        if user_roles:
            profile.user_role = user_roles[0]
        profile.save()

        user = profile.username
        submitted_pairs = set()

        for role_val, app_id, perm_type in zip(user_roles, app_ids, perm_types):
            app_id_int = int(app_id)
            submitted_pairs.add((app_id_int, perm_type))
            
            application = Application.objects.filter(id=app_id_int).first()
            if application:
                existing_perm = Permission.objects.filter(user=user, application=application).first()
                
                if existing_perm:
                    if existing_perm.permission_type != perm_type or existing_perm.role != role_val:
                        existing_perm.permission_type = perm_type
                        existing_perm.role = role_val
                        
                        existing_perm.approval_status = 'pending'
                        existing_perm.is_active = False
                            
                        existing_perm.save()
                else:
                    Permission.objects.create(
                        user=user,
                        application=application,
                        permission_type=perm_type,
                        role=role_val,
                        is_active=False, 
                        approval_status='pending' 
                    )

        permissions_to_remove = []
        for existing_perm in Permission.objects.filter(user=user):
            if (existing_perm.application_id, existing_perm.permission_type) not in submitted_pairs:
                permissions_to_remove.append(existing_perm)
        
        if permissions_to_remove:
            if profile.is_active:
                messages.error(request, "Action Blocked: You cannot delete existing access rows while the user profile is active. Please deactivate the user first.")
                return redirect('user_management')
            else:
                for perm in permissions_to_remove:
                    perm.delete()

        messages.success(request, "User profile updated. Role modifications have been sent to pending approval.")

    return redirect('user_management')


@never_cache 
@login_required(login_url='portal_login')
@auth_manager_access_required
def app_management(request):
    permissions = Permission.objects.select_related('user', 'application', 'application__app_type').all()
    applications = Application.objects.select_related('app_type').order_by('-created_at')
    auth_types  = Authenticationtype.objects.all()

    is_checker = has_auth_manager_permission(request.user, 2) and not has_auth_manager_permission(request.user, 3)

    return render(request, 'base/apps.html', {
        'permissions': permissions, 
        'applications': applications, 
        'auth_types': auth_types,
        'is_checker': is_checker,
        'can_approve': can_approve(request.user) 
    })

@never_cache 
@login_required(login_url='portal_login')
def add_app(request):

    is_admin = has_auth_manager_permission(request.user, 3)
    is_checker = has_auth_manager_permission(request.user, 2) and not is_admin
    is_maker = has_auth_manager_permission(request.user, 1) and not is_admin and not is_checker

    if is_admin or is_maker:
        can_add = True
    elif is_checker:
        can_add = False
    else:
        can_add = False

    if not can_add:
        log_action(
            request.user, 'access_denied', request.path, 
            'Checker attempted to register a new application', get_client_ip(request)
        )
        messages.error(request, 'Access Denied: Checkers are not authorized to register new applications.')
        return redirect('app_management')

    if request.method == 'POST':
        app_name    = request.POST.get('app_name', '').strip()
        app_id      = request.POST.get('app_id', '').strip()
        description = request.POST.get('description', '').strip()
        app_type_id = request.POST.get('app_type')
        ip          = get_client_ip(request)

        status_val  = 'pending'

        if Application.objects.filter(app_id=app_id).exists():
            messages.error(request, f"Failed: An application with App ID '{app_id}' already exists.")
            return redirect('app_management')

        app_type = Authenticationtype.objects.filter(id=app_type_id).first() if app_type_id else None
        login_url = request.POST.get('login_url', '').strip() or None
        
        raw_secret = secrets.token_hex(32)

        Application.objects.create(
            app_name=app_name, 
            app_id=app_id,
            description=description, 
            app_type=app_type, 
            status=status_val,
            app_secret=hash_app_secret(raw_secret),
            login_url=login_url
        )
        
        log_action(
            performed_by=request.user, action='app_created',
            target=app_name, details=f'App ID: {app_id} (Pending Approval)', ip_address=ip
        )
                   
        messages.success(request, f"Application '{app_name}' created and is pending Checker approval.")
        messages.warning(request, f"Client Secret (copy now — this will not be shown again): {raw_secret}")
        return redirect('app_management')

    auth_types = Authenticationtype.objects.all()
    return render(request, 'base/apps.html', {'auth_types': auth_types})

ALLOWED_APP_STATUS_VALUES = {'approved', 'rejected'}

@login_required(login_url='portal_login')
@require_POST
def toggle_app_status(request, app_id, new_status):

    if not can_approve(request.user):
        messages.error(request, "Access Denied: Only Checkers or Admins can approve/reject applications.")
        return redirect('app_management')

    if new_status not in ALLOWED_APP_STATUS_VALUES:
        return HttpResponseBadRequest("Invalid status value. Allowed values: approved, rejected.")

    app = get_object_or_404(Application, id=app_id)
    app.status = new_status
    app.save()
    
    log_action(
        performed_by=request.user,
        action='app_approved' if new_status == 'approved' else 'app_rejected',
        target=app.app_name, details=f'Status changed to {new_status}',
        ip_address=get_client_ip(request)
    )
    
    messages.success(request, f"Application '{app.app_name}' status successfully updated to {new_status}.")
    return redirect('app_management')


@login_required(login_url='portal_login')
@require_POST
def activate_profile(request, profile_id):
    if not has_auth_manager_permission(request.user, 3):
        log_action(request.user, 'access_denied', f'Profile {profile_id}', 'Non-admin attempted to activate an account', get_client_ip(request))
        messages.error(request, 'Access Denied: Only Admins can activate accounts.')
        return redirect('user_management')

    profile = get_object_or_404(Profile, id=profile_id)
    profile.is_active   = True
    profile.user_status = 'active'
    profile.save()
    
    user = profile.username
    user.is_active = True
    user.save()
    
    log_action(performed_by=request.user, action='user_activated',
               target=user.username, ip_address=get_client_ip(request))
               
    messages.success(request, f"Account for '{user.username}' successfully activated.")
    return redirect('user_management')


@login_required(login_url='portal_login')
@require_POST
def deactivate_profile(request, profile_id):
    if not has_auth_manager_permission(request.user, 3):
        log_action(request.user, 'access_denied', f'Profile {profile_id}', 'Non-admin attempted to deactivate an account', get_client_ip(request))
        messages.error(request, 'Access Denied: Only Admins can deactivate accounts.')
        return redirect('user_management')

    profile = get_object_or_404(Profile, id=profile_id)
    profile.is_active   = False
    profile.user_status = 'inactive'
    profile.save()
    
    user = profile.username
    user.is_active = False
    user.save()
    
    log_action(performed_by=request.user, action='user_deactivated',
               target=profile.username.username, ip_address=get_client_ip(request))
               
    messages.warning(request, f"Account for '{profile.username.username}' has been deactivated.")
    return redirect('user_management')


@login_required(login_url='portal_login')
@require_POST
def reset_attempts(request, profile_id):
    if not has_auth_manager_permission(request.user, 3):
        log_action(request.user, 'access_denied', f'Profile {profile_id}', 'Non-admin attempted to reset login attempts', get_client_ip(request))
        messages.error(request, 'Access Denied: Only Admins can reset login attempts.')
        return redirect('user_management')
    
    if not (request.user.is_superuser or has_auth_admin):
        log_action(request.user, 'access_denied', f'Profile {profile_id}', 'Non-admin attempted to reset login attempts', get_client_ip(request))
        messages.error(request, 'Access Denied: Only Admins can reset login attempts.')
        return redirect('user_management')

    profile = get_object_or_404(Profile, id=profile_id)
    profile.failed_login_attempts = 0
    profile.is_locked = False  
    profile.save()
    
    cache.delete(f"account_lockout_{profile.username.username}")
    
    log_action(performed_by=request.user, action='reset_attempts',
               target=profile.username.username, ip_address=get_client_ip(request))
               
    messages.info(request, f"Failed login attempts reset for '{profile.username.username}'.")
    return redirect('user_management')


@login_required(login_url='portal_login')
@auth_manager_access_required
def login_logs(request):
    logs_list = AuthTrail.objects.filter(status='success').select_related('user').order_by('-created_at')
    
    paginator = Paginator(logs_list, 15)
    
    page_number = request.GET.get('page', 1)
    logs = paginator.get_page(page_number)
    
    page_range = paginator.get_elided_page_range(number=page_number, on_each_side=2, on_ends=1)
    
    return render(request, 'base/login_logs.html', {
        'logs': logs,
        'page_range': page_range
    })

@login_required(login_url='portal_login')
@auth_manager_access_required
def failed_attempts(request):
    attempts_list = AuthTrail.objects.filter(status='failed').select_related('user').order_by('-created_at')
    
    paginator = Paginator(attempts_list, 15)
    
    page_number = request.GET.get('page', 1)
    attempts = paginator.get_page(page_number)
    
    page_range = paginator.get_elided_page_range(number=page_number, on_each_side=2, on_ends=1)
    
    return render(request, 'base/failed_attempts.html', {
        'attempts': attempts,
        'page_range': page_range
    })
@never_cache 
@login_required(login_url='portal_login')
def active_sessions(request):
    if not has_auth_manager_permission(request.user, 3):
        messages.error(request, 'Access Denied: Ordinary users cannot view active sessions.')
        return redirect('dashboard')

    from django.contrib.sessions.models import Session
    active = Session.objects.filter(expire_date__gte=timezone.now())
    sessions = []
    
    for s in active:
        data = s.get_decoded()
        uid = data.get('_auth_user_id')
        if uid:
            try:
                user = User.objects.get(id=uid)
                profile = Profile.objects.filter(username=user).first()
                trail = AuthTrail.objects.filter(user=user, status='success').order_by('-created_at').first()
                
                opaque_id = str(uuid.uuid4())
                cache.set(f"session_map_{opaque_id}", s.session_key, timeout=3600) # Map valid for 1 hour

                sessions.append({
                    'username': user.username,
                    'fullname': f"{profile.firstname or ''} {profile.lastname or ''}".strip() if profile else '—',
                    'role': profile.user_role if profile else '—',
                    'ip_address': trail.ip_address if trail else '—',
                    'login_time': trail.created_at if trail else None,
                    'management_id': opaque_id, # Safe, opaque token sent to frontend (NO raw session keys)
                    'expire_date': s.expire_date,
                })
            except User.DoesNotExist:
                pass
                
    return render(request, 'base/active_sessions.html', {'sessions': sessions})

@login_required(login_url='portal_login')
@require_POST 
def force_logout(request, management_id):
    if not has_auth_manager_permission(request.user, 3):
        messages.error(request, 'Access Denied: Unauthorized to terminate sessions.')
        return redirect('dashboard')

    from django.contrib.sessions.models import Session
    
    session_key = cache.get(f"session_map_{management_id}")
    
    if not session_key:
        messages.error(request, "Invalid or expired session management reference.")
        return redirect('active_sessions')

    try:
        Session.objects.get(session_key=session_key).delete()
        cache.delete(f"session_map_{management_id}") # Clear mapping after use
        messages.success(request, "Active session forcefully terminated.")
    except Session.DoesNotExist:
        messages.error(request, "Session not found or already expired.")
        
    return redirect('active_sessions')


@never_cache 
@login_required(login_url='portal_login')
def audit_log(request):
    if not has_auth_manager_permission(request.user, 3):
        log_action(request.user, 'access_denied', request.path, 'Non-admin attempted to view audit logs', get_client_ip(request))
        messages.error(request, 'Access Denied: Only Admins can view audit logs.')
        return redirect('user_management')

    logs = AuditLog.objects.select_related('performed_by').all().order_by('-created_at')
    return render(request, 'base/audit_log.html', {'logs': logs})


@never_cache 
@login_required(login_url='portal_login')
def user_access_control(request):
    if not has_auth_manager_permission(request.user, 3):
        messages.error(request, 'Access Denied: Makers and Checkers are not authorized to view the Roles & Permissions matrix.')
        return redirect('dashboard')
        
    profiles = Profile.objects.select_related('username').all()
    return render(request, 'base/user_access_control.html', {'profiles': profiles})

@never_cache 
@login_required(login_url='portal_login')
def app_access_policies(request):
    if not has_auth_manager_permission(request.user, 3):
        messages.error(request, 'Access Denied: Makers and Checkers are not authorized to view the Policies matrix.')
        return redirect('dashboard')
        
    applications = Application.objects.select_related('app_type').all()
    permissions  = Permission.objects.select_related('user', 'application').all()
    return render(request, 'base/app_access_policies.html', {
        'applications': applications, 'permissions': permissions,
    })

@never_cache 
@login_required(login_url='portal_login')
def batch_permission_action(request):
    if request.method == 'POST':
        if not can_approve(request.user):
            messages.error(request, "You do not have the required role to approve/reject permissions.")
            return redirect('user_management')

        action = request.POST.get('action') 
        perm_ids = request.POST.getlist('perm_ids[]')

        if not perm_ids:
            messages.warning(request, "No permissions were selected.")
            return redirect('user_management')

        permissions = Permission.objects.filter(id__in=perm_ids)
        count = permissions.count()

        if action == 'approve':
            permissions.update(
                approval_status='approved',
                is_active=True,
                approved_by=request.user,
                approved_at=timezone.now()
            )
            messages.success(request, f"Successfully approved {count} permission(s).")
            
            for p in permissions:
                if p.application and p.application.app_type:
                    app_type_name = p.application.app_type.name.upper()
                    if 'DB' in app_type_name or 'LOCAL' in app_type_name:
                        user = p.user
                        profile = user.profile

                        user.set_unusable_password()
                        user.save()
                        
                        if profile.auth_type == 'AD':
                            profile.auth_type = 'Hybrid'
                        elif not profile.auth_type:
                            profile.auth_type = 'DB'

                        profile.requires_password_reset = True
                        profile.save(update_fields=['requires_password_reset', 'auth_type'])

                        token = signing.dumps(
                            {"perm_id": p.id, "username": user.username},
                            salt='app-credential-activation'
                        )
                        
                        app_login_url = p.application.login_url if p.application and p.application.login_url else None
                        
                        if app_login_url:
                            clean_url = app_login_url.rstrip('/')
                            activation_link = f"{clean_url}?activation_token={token}"
                        else:
                            activation_link = request.build_absolute_uri(
                                reverse('activate_app_credentials', args=[token])
                            )

                        notify_message = (
                            f"Dear {profile.firstname or user.username},\n\n"
                            f"You have been granted access to {p.application.app_name}. "
                            f"Use the link below to activate your login. This link is single-use "
                            f"and expires in 10 minutes:\n\n"
                            f"{activation_link}\n\n"
                            f"NOTE: This does not affect your existing login for any other application.\n\n"
                            f"Thank you,\nPrudential Bank Ltd."
                        )

                        try:
                            sms_helper(profile.phone, notify_message)
                            mail_helper(profile.email, notify_message)
                        except Exception:
                            pass
                
                log_action(request.user, 'permission_approved', p.user.username, f'Approved {p.permission_type} for {p.application.app_name}', get_client_ip(request))
                
        elif action == 'reject':
            permissions.update(
                approval_status='rejected',
                is_active=False,
                approved_by=request.user,
                approved_at=timezone.now()
            )
            messages.success(request, f"Successfully rejected {count} permission(s).")
            for p in permissions:
                log_action(request.user, 'permission_rejected', p.user.username, f'Rejected {p.permission_type} for {p.application.app_name}', get_client_ip(request))
                
    return redirect('user_management')

@method_decorator([never_cache, csrf_exempt], name="dispatch")
class ChangePasswordView(APIView):
    throttle_classes = [AnonRateThrottle, UserRateThrottle]

    def post(self, request):
        username = request.data.get('username')
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        app_id = request.data.get('app_id') # <-- NEW: Extract app_id

        if not all([username, old_password, new_password, app_id]):
            return JsonResponse({'message': 'Username, app_id, old password, and new password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        generic_error = JsonResponse(
            {'message': 'Password change failed: Invalid username or current password.'}, 
            status=status.HTTP_401_UNAUTHORIZED
        )

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return generic_error

        profile = getattr(user, 'profile', None)
        if not profile:
            return generic_error

        if profile.auth_type != 'DB':
            return JsonResponse({'message': 'Active Directory users must change their passwords through the central IT portal.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            application = Application.objects.get(app_id=app_id, status='approved')
            permission_record = Permission.objects.get(
                user=user, 
                application=application, 
                is_active=True, 
                approval_status='approved'
            )
        except (Application.DoesNotExist, Permission.DoesNotExist):
            return generic_error

        if not permission_record.check_password(old_password):
            return generic_error

        recent_history = PasswordHistory.objects.filter(user=user).order_by('-created_at')[:4]
        for record in recent_history:
            if check_password(new_password, record.password_hash):
                return JsonResponse({'message': 'Compliance Violation: You cannot reuse any of your last 4 passwords.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_password(new_password, user=user)
        except ValidationError as e:
            return JsonResponse({'message': ' '.join(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

        permission_record.set_password(new_password)
        permission_record.requires_password_reset = False
        permission_record.save()
        
        profile.password_last_updated = timezone.now()
        profile.save(update_fields=['password_last_updated'])

        PasswordHistory.objects.create(user=user, password_hash=make_password(new_password))

        AuditLog.objects.create(
            action='password_changed',
            target=f"{username} ({application.name})",
            details=f'User successfully changed their isolated password for {application.name}.',
            ip_address=get_client_ip(request)
        )

        return JsonResponse({'message': 'Password updated successfully. You may now log in.'}, status=status.HTTP_200_OK)

@never_cache 
@login_required(login_url='portal_login')
def portal_update_password(request):
    user = request.user
    profile = getattr(user, 'profile', None)

    if not profile or profile.auth_type == 'AD':
        messages.error(request, "Active Directory users must manage passwords through the central IT portal.")
        return redirect('user_management')

    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not all([old_password, new_password, confirm_password]):
            messages.error(request, "All fields are required.")
            return render(request, 'portal/update_password.html')

        if not user.check_password(old_password):
            messages.error(request, "Incorrect current password.")
            return render(request, 'portal/update_password.html')

        if new_password != confirm_password:
            messages.error(request, "New passwords do not match.")
            return render(request, 'portal/update_password.html')

        recent_history = PasswordHistory.objects.filter(user=user).order_by('-created_at')[:4]
        for record in recent_history:
            if check_password(new_password, record.password_hash):
                messages.error(request, "Compliance Violation: You cannot reuse any of your last 4 passwords.")
                return render(request, 'portal/update_password.html')

        try:
            validate_password(new_password, user=user)
        except ValidationError as e:
            messages.error(request, ' '.join(e.messages))
            return render(request, 'portal/update_password.html')

        user.set_password(new_password)
        user.save()
        
        PasswordHistory.objects.create(user=user, password_hash=user.password)

        profile.requires_password_reset = False
        profile.password_last_updated = timezone.now()
        profile.save()

        log_action(
            performed_by=request.user,
            action='portal_password_changed',
            target=user.username,
            details=f'User {user.username} updated their password via the portal.',
            ip_address=get_client_ip(request)
        )

        logout(request) 
        messages.success(request, "Password successfully updated! Please log in with your new password.")
        return redirect('portal_login') 

    return render(request, 'portal/update_password.html')

@never_cache 
@login_required(login_url='portal_login')
@auth_manager_access_required
def application_access(request):
    applications = Application.objects.select_related('app_type').order_by('-created_at')
    auth_types   = Authenticationtype.objects.all()
    
    is_admin = has_auth_manager_permission(request.user, 3)
    is_checker = has_auth_manager_permission(request.user, 2) and not is_admin
    is_maker = has_auth_manager_permission(request.user, 1) and not is_admin and not is_checker
    is_checker_db = is_checker

    if is_admin:
        ui_can_add = True
        ui_can_approve = False
        ui_is_checker = False
        ui_is_admin = True
    elif is_maker:
        ui_can_add = True
        ui_can_approve = False
        ui_is_checker = False
        ui_is_admin = False
    elif is_checker_db:
        ui_can_add = False
        ui_can_approve = True
        ui_is_checker = True
        ui_is_admin = False
    else:
        ui_can_add = False
        ui_can_approve = False
        ui_is_checker = False
        ui_is_admin = False

    return render(request, 'base/application_access.html', {
        'applications': applications,
        'auth_types': auth_types,
        'is_checker': ui_is_checker,
        'is_admin': ui_is_admin,
        'can_approve': ui_can_approve,
        'can_add_app': ui_can_add, 
    })


@never_cache 
@login_required(login_url='portal_login')
def edit_app(request, app_id):
    if request.method == 'POST':
        app = get_object_or_404(Application, id=app_id)
        
        is_admin = has_auth_manager_permission(request.user, 3)
        is_checker = has_auth_manager_permission(request.user, 2) and not is_admin
        is_maker = has_auth_manager_permission(request.user, 1) and not is_admin and not is_checker

        if is_admin or is_maker:
            can_approve = False
        elif is_checker:
            can_approve = True
        else:
            can_approve = False

        new_status = request.POST.get('status')
        if not can_approve and new_status and new_status in ['approved', 'rejected']:
            print(f"BLOCKED! {request.user.username} tried to approve/reject an app.")
            messages.error(request, "Access Denied: Only Checkers are permitted to approve or reject applications.")
            return redirect('application_access')

        app.app_name    = request.POST.get('app_name', app.app_name).strip()
        app.app_id      = request.POST.get('app_id', app.app_id).strip()
        app.description = request.POST.get('description', '').strip()
        app.login_url   = request.POST.get('login_url', '').strip() or None
        
        type_id = request.POST.get('app_type')
        if type_id:
            app.app_type = Authenticationtype.objects.filter(id=type_id).first()

        if can_approve and new_status:
            app.status = new_status
        else:
            app.status = 'pending' 

        app.save()
        messages.success(request, f"Application '{app.app_name}' updated successfully.")
        
    return redirect('application_access')


@login_required(login_url='portal_login')
@admin_required(min_weight=3)
@require_POST
def delete_app(request, app_id):
    application = get_object_or_404(Application, id=app_id)
    
    log_action(
        performed_by=request.user, 
        action='application_deleted',
        target=application.app_name,
        details=f'Application {application.app_name} was deleted.',
        ip_address=get_client_ip(request)
    )
    
    application.delete()
    messages.success(request, "Application deleted successfully.")
    return redirect('app_management')

@login_required(login_url='portal_login')
@admin_required(min_weight=3)
@require_POST  
def delete_user(request, perm_id):
    if not has_auth_manager_permission(request.user, 3):
        log_action(request.user, 'access_denied', f'Permission {perm_id}', 'Maker/Checker attempted to delete a permission', get_client_ip(request))
        messages.error(request, 'Access Denied: Only Admins and Super Admins can remove user permissions.')
        return redirect('user_management')

    perm = get_object_or_404(Permission, id=perm_id)
    log_action(performed_by=request.user, action='permission_revoked',
               target=perm.user.username,
               details=f'Permission removed from {perm.application.app_name}',
               ip_address=get_client_ip(request))
    perm.delete()
    messages.success(request, "User permission deleted successfully.")
    return redirect('user_management')

@login_required
@auth_manager_access_required
def iam_admins_view(request):
    iam_admins_list = Permission.objects.filter(
        permission_type__in=['admin', 'maker', 'checker'],
        application__app_id='AUTH_MANAGER'  # <-- THIS IS THE NEW LOCK
    ).select_related('user', 'user__profile', 'approved_by')

    paginator = Paginator(iam_admins_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'iam_admins': page_obj
    }
    return render(request, 'base/iam_admins.html', context)

def activate_account(request, uidb64, token):
    """
    Single-use, short-lived account activation / credential-set link.
    AUTH-008 remediation — replaces plaintext temporary passwords.
    Public/unauthenticated by design, same as Django's built-in
    password-reset-confirm view.
    """
    if is_rate_limited(f"activate_account_ip_{get_client_ip(request)}", limit=20, window_seconds=60):
        return render(request, 'portal/activate_account.html', {'invalid_link': True})

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        return render(request, 'portal/activate_account.html', {'invalid_link': True})

    profile = getattr(user, 'profile', None)

    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not new_password or not confirm_password:
            messages.error(request, "Both password fields are required.")
            return render(request, 'portal/activate_account.html', {'uidb64': uidb64, 'token': token})

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'portal/activate_account.html', {'uidb64': uidb64, 'token': token})

        recent_history = PasswordHistory.objects.filter(user=user).order_by('-created_at')[:4]
        for record in recent_history:
            if check_password(new_password, record.password_hash):
                messages.error(request, "You cannot reuse a recent password.")
                return render(request, 'portal/activate_account.html', {'uidb64': uidb64, 'token': token})

        try:
            validate_password(new_password, user=user)
        except ValidationError as e:
            messages.error(request, ' '.join(e.messages))
            return render(request, 'portal/activate_account.html', {'uidb64': uidb64, 'token': token})

        user.set_password(new_password)
        user.save()

        PasswordHistory.objects.create(user=user, password_hash=user.password)

        if profile:
            profile.requires_password_reset = False
            profile.password_last_updated = timezone.now()
            profile.save(update_fields=['requires_password_reset', 'password_last_updated'])

        log_action(
            performed_by=user, action='account_activated',
            target=user.username,
            details='User set their password via a single-use activation link.',
            ip_address=get_client_ip(request)
        )

        messages.success(request, "Your password has been set. You may now log in.")
        return redirect('portal_login')

    return render(request, 'portal/activate_account.html', {'uidb64': uidb64, 'token': token})

APP_CREDENTIAL_LINK_MAX_AGE = 600  

def activate_app_credentials(request, token):
    """
    Single-use, 10-minute link. 
    AUTH-008 remediation: Replaced auto-generated plaintext password 
    dispatch with a POST-based user-set password form.
    """
    if is_rate_limited(f"activate_app_creds_ip_{get_client_ip(request)}", limit=20, window_seconds=60):
        return render(request, 'portal/activate_app_credentials.html', {'invalid_link': True})

    try:
        data = signing.loads(token, salt='app-credential-activation', max_age=APP_CREDENTIAL_LINK_MAX_AGE)
        perm = Permission.objects.select_related('user', 'user__profile', 'application').get(id=data['perm_id'])
    except (signing.BadSignature, Permission.DoesNotExist, KeyError):
        return render(request, 'portal/activate_app_credentials.html', {'invalid_link': True})

    if data.get('username') != perm.user.username:
        return render(request, 'portal/activate_app_credentials.html', {'invalid_link': True})

    if perm.credentials_sent:
        return render(request, 'portal/activate_app_credentials.html', {'invalid_link': True})

    user = perm.user
    profile = getattr(user, 'profile', None)
    app_name = perm.application.app_name if perm.application else 'your application'
    app_login_url = perm.application.login_url if perm.application else None

    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not new_password or new_password != confirm_password:
            messages.error(request, "Passwords do not match or are empty.")
            return render(request, 'portal/activate_app_credentials.html', {'token': token, 'app_name': app_name})

        perm.set_password(new_password)
        perm.credentials_sent = True
        perm.save()

        log_action(
            performed_by=user, action='app_credentials_activated',
            target=user.username,
            details=f'Isolated password for {app_name} securely set by user via single-use link.',
            ip_address=get_client_ip(request)
        )

        return render(request, 'portal/activate_app_credentials.html', {
            'success': True, 'app_name': app_name, 'app_login_url': app_login_url
        })

    return render(request, 'portal/activate_app_credentials.html', {
        'token': token, 'app_name': app_name
    })


@csrf_exempt
def api_activate_credentials(request):
    """
    API endpoint for standalone apps to trigger the password generation and SMS.
    The standalone app sends the token here via a server-to-server POST request.
    """
    if request.method == 'OPTIONS':
        response = JsonResponse({'status': 'ok'})
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    if request.method != 'POST':
        response = JsonResponse({'error': 'Only POST allowed'}, status=405)
        response['Access-Control-Allow-Origin'] = '*'
        return response

    token = request.POST.get('token') or request.GET.get('token')
    if not token:
        response = JsonResponse({'error': 'Missing token'}, status=400)
        response['Access-Control-Allow-Origin'] = '*'
        return response

    try:
        data = signing.loads(token, salt='app-credential-activation', max_age=600)
        perm = Permission.objects.select_related('user', 'user__profile', 'application').get(id=data['perm_id'])
    except (signing.BadSignature, Permission.DoesNotExist, KeyError):
        response = JsonResponse({'error': 'Invalid or expired link'}, status=400)
        response['Access-Control-Allow-Origin'] = '*'
        return response

    if perm.credentials_sent:
        response = JsonResponse({'error': 'Link has already been used'}, status=400)
        response['Access-Control-Allow-Origin'] = '*'
        return response

    user = perm.user
    profile = getattr(user, 'profile', None)
    app_name = perm.application.app_name if perm.application else 'your application'

    
    placeholder = signing.dumps({"perm_id": perm.id, "purpose": "placeholder"})
    perm.set_password(placeholder)
    perm.credentials_sent = True
    perm.save()

    activation_token = signing.dumps({"perm_id": perm.id}, salt=CREDENTIAL_LINK_SALT)
    activation_link = f"{BASE_ACTIVATION_URL}/portal/activate-credentials/{activation_token}/"
    
    greeting_name = profile.firstname if profile and profile.firstname else user.username
    message = (
        f"Dear {greeting_name},\n\n"
        f"You have been granted access to {app_name} on Auth Manager. "
        f"Set your password for this application using the link below. "
        f"This link is single-use and expires in 24 hours:\n\n"
        f"{activation_link}\n\n"
        f"Application: {app_name}\n"
        f"Username: {user.username}\n\n"
        f"Thank you,\nPrudential Bank Ltd."
    )


    try:
        sms_helper(profile.phone if profile else None, message)
        mail_helper(profile.email if profile else None, message)
    except Exception:
        pass 

    response = JsonResponse({'success': True, 'message': 'Activation link generated and sent to customer.'})
    response['Access-Control-Allow-Origin'] = '*'
    return response

@never_cache
def portal_otp_verify(request):
    user_id = request.session.get('pre_2fa_user_id')
    if not user_id:
        return redirect('portal_login')

    user = get_object_or_404(User, id=user_id)
    profile = getattr(user, 'profile', None)

    error = None
    if request.method == 'POST':
        submitted_otp = request.POST.get('otp_code', '').strip()
        
        valid_otp = cache.get(f"otp_auth_{user.id}")

        if not valid_otp:
            error = "Your code has expired. Please log in again to request a new one."
            request.session.flush() 
        elif submitted_otp == valid_otp:
            cache.delete(f"otp_auth_{user.id}")
            del request.session['pre_2fa_user_id']
            
            login(request, user)
            profile.last_login = timezone.now()
            profile.failed_login_attempts = 0
            profile.save()
            
            ip = get_client_ip(request)
            agent = request.META.get('HTTP_USER_AGENT', '')[:255]
            AuthTrail.objects.create(user=user, username=user.username, status='success', ip_address=ip, user_agent=agent)
            
            if profile.auth_type == 'DB' and profile.requires_password_reset:
                return redirect('portal_update_password')

            messages.success(request, f"Welcome back, {user.username}! You have logged in successfully.")
            return redirect('dashboard')
        else:
            error = "Invalid code. Please try again."
            
    return render(request, 'pages/otp_verify.html', {
        'error': error, 
        'obfuscated_phone': f"********{profile.phone[-4:]}" if profile and profile.phone else None
    })

@csrf_exempt 
def api_otp_verify(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            temp_token = data.get('temp_token', '').strip()
            submitted_otp = data.get('otp_code', '').strip()
            
            if not temp_token or not submitted_otp:
                return JsonResponse({"error": "Missing temp_token or otp_code"}, status=400)
                
            cache_data = cache.get(f"api_otp_data_{temp_token}")
            valid_otp = cache.get(f"api_otp_code_{temp_token}")
            
            if not cache_data or not valid_otp:
                return JsonResponse({"error": "OTP session expired or invalid. Please log in again."}, status=401)
                
            if str(submitted_otp) == str(valid_otp):
                
                cache.delete(f"api_otp_data_{temp_token}")
                cache.delete(f"api_otp_code_{temp_token}")
                
                user_id = cache_data.get('user_id')
                user = User.objects.get(id=user_id)
                
                refresh = RefreshToken.for_user(user)
                
                return JsonResponse({
                    "status": "success",
                    "message": "Authentication successful",
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                    "user_id": user.id,
                    "username": cache_data.get('username'),
                    "role": cache_data.get('role')
                }, status=200)
                
            else:
                return JsonResponse({"error": "Invalid OTP code."}, status=401)
                
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)
            
    return JsonResponse({"error": "Method not allowed"}, status=405)

class VerifyOTPView(APIView):
    throttle_classes = [LoginBruteForceThrottle, LoginIPThrottle]

    def post(self, request):
        temp_token = request.data.get('temp_token')
        submitted_otp = request.data.get('otp_code')
        client_ip = get_client_ip(request)
        
        if not temp_token or not submitted_otp:
            return JsonResponse(
                {'message': 'Missing temp_token or otp_code.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        valid_otp = cache.get(f"api_otp_code_{temp_token}")
        cache_data = cache.get(f"api_otp_data_{temp_token}")
        
        if not valid_otp or not cache_data:
            return JsonResponse(
                {'message': 'OTP session expired or invalid. Please log in again.'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
            
        if submitted_otp != valid_otp:
            
            return JsonResponse(
                {'message': 'Invalid OTP code.'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
         
        cache.delete(f"api_otp_code_{temp_token}")
        cache.delete(f"api_otp_data_{temp_token}")
        
        try:
            user = User.objects.get(id=cache_data['user_id'])
            profile = getattr(user, 'profile', None)
        except User.DoesNotExist:
            return JsonResponse({'message': 'Authentication failed.'}, status=status.HTTP_401_UNAUTHORIZED)
            
        profile.last_login = timezone.now()
        profile.save(update_fields=['last_login'])
        
        AuditLog.objects.create(
            action='api_login_success',
            target=cache_data['username'],
            details='Successful 2FA API login',
            ip_address=client_ip
        )
        
        if cache_data['is_local_app'] and cache_data['requires_password_reset']:
            new_password_encrypted = request.data.get('new_password')
            
            if new_password_encrypted:
                new_password_plain = decrypt_payload(new_password_encrypted)
                if new_password_plain:
                    app_id = request.data.get('app_id')
                    perm_record = Permission.objects.filter(user=user, application__app_id=app_id).first()
                    
                    if perm_record:
                        perm_record.set_password(new_password_plain)
                        perm_record.requires_password_reset = False
                        perm_record.save()
                        
                        return JsonResponse({
                            'message': 'Password successfully updated and login successful',
                            'permission_type': cache_data['permission_type'],
                            'role': cache_data['role']
                        }, status=status.HTTP_200_OK)
            
            return JsonResponse({
                'message': 'Password reset required.',
                'action_required': 'reset_password',
                'username': cache_data['username'],
                'temp_token': temp_token 
            }, status=status.HTTP_202_ACCEPTED)

        return JsonResponse({
            'message': 'Login successful',
            'permission_type': cache_data['permission_type'],
            'role': cache_data['role']
        }, status=status.HTTP_200_OK)