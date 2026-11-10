import csv
from django.http import HttpResponse
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from rest_framework_simplejwt.token_blacklist import models as blacklist_models

from .models import Profile, Application, Permission, Authenticationtype, AuthTrail, AuditLog


@admin.action(description='Export Selected to CSV/Excel')
def export_to_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="application_users_export.csv"'

    writer = csv.writer(response)
    writer.writerow(['Username', 'Application Name', 'App ID', 'Permission Type', 'Role', 'Approval Status', 'Is Active'])

    for obj in queryset:
        writer.writerow([
            obj.user.username if obj.user else 'N/A',
            obj.application.app_name if obj.application else 'N/A',
            obj.application.app_id if obj.application else 'N/A',
            obj.permission_type,
            obj.role,
            obj.approval_status,
            obj.is_active
        ])

    return response


admin.site.register(Profile)
admin.site.register(Authenticationtype)


class PermissionInline(admin.TabularInline):
    model = Permission
    extra = 0  
    can_delete = False 
    readonly_fields = ('user', 'permission_type', 'role', 'approval_status')
    fields = ('user', 'permission_type', 'role', 'approval_status', 'is_active')

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('app_name', 'app_id', 'status', 'created_at') 
    search_fields = ('app_name', 'app_id')
    exclude = ('app_secret',)
    readonly_fields = ('created_at', 'updated_at')
    
    inlines = [PermissionInline]

@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'application', 'permission_type', 'role', 'approval_status', 'is_active')
    list_filter = ('application', 'permission_type', 'approval_status', 'is_active')
    search_fields = ('user__username', 'application__app_name', 'application__app_id')
    
    actions = [export_to_csv]


@admin.register(AuthTrail)
class AuthTrailAdmin(admin.ModelAdmin):
    list_display = ('username', 'status', 'app_id', 'ip_address', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('username', 'ip_address', 'reason', 'user_agent', 'app_id')
    date_hierarchy = 'created_at'
    readonly_fields = ('user', 'username', 'app_id', 'status', 'reason', 'ip_address', 'user_agent', 'created_at')

    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('performed_by', 'action', 'target', 'ip_address', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('performed_by__username', 'action', 'target', 'details', 'ip_address')
    date_hierarchy = 'created_at'
    readonly_fields = ('performed_by', 'action', 'target', 'details', 'ip_address', 'created_at')

    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False

try:
    admin.site.unregister(blacklist_models.OutstandingToken)
except admin.sites.NotRegistered:
    pass

try:
    admin.site.unregister(blacklist_models.BlacklistedToken)
except admin.sites.NotRegistered:
    pass

@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ('action_time', 'user', 'content_type', 'object_repr', 'action_flag', 'change_message')
    list_filter = ('action_time', 'user', 'content_type')
    search_fields = ('object_repr', 'change_message')
    list_per_page = 25  
    readonly_fields = ('action_time', 'user', 'content_type', 'object_id', 'object_repr', 'action_flag', 'change_message')

    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False