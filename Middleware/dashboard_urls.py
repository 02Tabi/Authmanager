from django.urls import path
from .views import (
    portal_login, portal_logout, dashboard,
    user_management, add_user, delete_user,
    toggle_user_status, edit_user,
    approve_permission, reject_permission, batch_permission_action, 
    user_access_control, activate_profile,
    deactivate_profile, reset_attempts,
    app_management, add_app, delete_app, toggle_app_status,
    app_access_policies,
    login_logs, failed_attempts, active_sessions,
    audit_log, force_logout, activate_account,
    iam_admins_view,
    api_activate_credentials
)

urlpatterns = [
    path('login/',     portal_login,  name='portal_login'),
    path('logout/',    portal_logout, name='portal_logout'),
    path('dashboard/', dashboard,     name='dashboard'),

    path('users/',                                      user_management,     name='user_management'),
    path('users/add/',                                  add_user,            name='add_user'),
    path('users/delete/<int:perm_id>/',                 delete_user,         name='delete_user'),
    path('users/toggle/<int:perm_id>/<int:activate>/',  toggle_user_status,  name='toggle_user_status'),
    path('users/edit/<int:profile_id>/',                edit_user,           name='edit_user'),
    path('users/approve/<int:perm_id>/',                approve_permission,  name='approve_permission'),
    path('users/reject/<int:perm_id>/',                 reject_permission,   name='reject_permission'),
    path('users/access-control/',                       user_access_control, name='user_access_control'),
    path('users/activate/<int:profile_id>/',            activate_profile,    name='activate_profile'),
    path('users/deactivate/<int:profile_id>/',          deactivate_profile,  name='deactivate_profile'),
    path('users/reset-attempts/<int:profile_id>/',      reset_attempts,      name='reset_attempts'),
    
    path('users/batch-action/',                         batch_permission_action, name='batch_permission_action'),

    path('apps/',                                       app_management,      name='app_management'),
    path('apps/add/',                                   add_app,             name='add_app'),
    path('apps/delete/<int:app_id>/',                   delete_app,          name='delete_app'),
    path('apps/toggle/<int:app_id>/<str:new_status>/',  toggle_app_status,   name='toggle_app_status'),
    path('apps/access-policies/',                       app_access_policies, name='app_access_policies'),

    path('auth-trail/login-logs/',                      login_logs,          name='login_logs'),
    path('auth-trail/failed-attempts/',                 failed_attempts,     name='failed_attempts'),
    path('auth-trail/active-sessions/',                 active_sessions,     name='active_sessions'),
    path('auth-trail/audit-log/',                       audit_log,           name='audit_log'),
    path('auth-trail/force-logout/<str:session_key>/',  force_logout,        name='force_logout'),
    
    path('iam-administrators/',                         iam_admins_view,     name='iam_admins'),
    path('activate/<str:uidb64>/<str:token>/', activate_account, name='activate_account'),
    path('api-activate-credentials/', api_activate_credentials, name='api_activate_credentials'),
]
