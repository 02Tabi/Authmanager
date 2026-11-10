from django.urls import path
from django.views.generic import RedirectView

from .views import (
    LoginView, portal_login, portal_logout, dashboard,
    user_management, app_management, add_user, delete_user,
    toggle_user_status, add_app, delete_app, toggle_app_status,
    user_access_control, app_access_policies, activate_profile,
    deactivate_profile, reset_attempts, edit_user,
    approve_permission, reject_permission, batch_permission_action, 
    login_logs, failed_attempts, active_sessions, audit_log, force_logout,
    application_access, edit_app, activate_account, activate_app_credentials, api_activate_credentials, ChangePasswordView, portal_update_password,portal_otp_verify,VerifyOTPView,
    iam_admins_view  
)

urlpatterns = [
    path('login/', LoginView.as_view(), name='api_login'),

    path('portal/login/',             portal_login,  name='portal_login'),
    path('portal/logout/',            portal_logout, name='portal_logout'),
    path('portal/dashboard/', dashboard,     name='dashboard'),

    path('portal/users/',                                              user_management,    name='user_management'),
    path('portal/users/add/',                                          add_user,           name='add_user'),
    path('portal/users/delete/<int:perm_id>/',                         delete_user,        name='delete_user'),
    path('portal/users/toggle/<int:perm_id>/<int:activate>/',  toggle_user_status, name='toggle_user_status'),
    path('portal/users/edit/<int:profile_id>/',                        edit_user,          name='edit_user'),
    path('portal/users/approve/<int:perm_id>/',                        approve_permission, name='approve_permission'),
    path('portal/users/reject/<int:perm_id>/',                         reject_permission,  name='reject_permission'),
    path('portal/users/access-control/',                               user_access_control, name='user_access_control'),
    path('portal/users/activate/<int:profile_id>/',            activate_profile,   name='activate_profile'),
    path('portal/users/deactivate/<int:profile_id>/',          deactivate_profile, name='deactivate_profile'),
    path('portal/users/reset-attempts/<int:profile_id>/',      reset_attempts,     name='reset_attempts'),
    
    path('portal/users/batch-action/',                         batch_permission_action, name='batch_permission_action'),

    path('portal/apps/',                                               app_management,     name='app_management'),
    path('portal/apps/add/',                                           add_app,            name='add_app'),
    path('portal/apps/delete/<int:app_id>/',                           delete_app,         name='delete_app'),
    path('portal/apps/toggle/<int:app_id>/<str:new_status>/',  toggle_app_status,  name='toggle_app_status'),
    path('portal/apps/access-policies/',                               app_access_policies, name='app_access_policies'),

    path('portal/auth-trail/login-logs/',                      login_logs,         name='login_logs'),
    path('portal/auth-trail/failed-attempts/',                 failed_attempts,    name='failed_attempts'),
    path('portal/auth-trail/active-sessions/',                 active_sessions,    name='active_sessions'),
    path('portal/auth-trail/audit-log/',                       audit_log,          name='audit_log'),
    path('portal/auth-trail/force-logout/<str:session_key>/',  force_logout,       name='force_logout'),
    
    path('change-password/', ChangePasswordView.as_view(),               name='api_change_password'),
    path('portal/update-password/', portal_update_password,                        name='portal_update_password'),
    path('favicon.ico', RedirectView.as_view(url='/static/img/pb_logo.png', permanent=True)),
    
    path('portal/application-access/', application_access, name='application_access'),
    path('portal/edit-app/<int:app_id>/', edit_app, name='edit_app'),
    path('iam-administrators/', iam_admins_view, name='iam_admins'),
    path('portal/activate/<str:uidb64>/<str:token>/', activate_account, name='activate_account'),
    path('portal/activate-credentials/<str:token>/', activate_app_credentials, name='activate_app_credentials'),
    path('portal/api-activate-credentials/', api_activate_credentials, name='api_activate_credentials'),
    path('otp-verify/', portal_otp_verify, name='portal_otp_verify'),
    path('login/verify/', VerifyOTPView.as_view(), name='api_otp_verify'),
]