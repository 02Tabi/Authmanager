def nav_items(request):
    nav = [
        {
            'type': 'item',
            'name': 'Dashboard',
            'url': '/portal/dashboard/',
            'icon': 'cil-speedometer',
        },
        {
            'type': 'title',
            'name': 'Authentication Manager',
        },
        {
            'type': 'group',
            'name': 'User Management',
            'icon': 'cil-people',
            'items': [
                {'name': 'Role & Permissions', 'url': '/portal/users/', 'icon': 'cil-lock-locked'},
                {'name': 'IAM Administrators', 'url': '/portal/iam-administrators/', 'icon': 'cil-shield-alt'},
            ],
        },
        {
            'type': 'group',
            'name': 'Application Management',
            'icon': 'cil-puzzle',
            'items': [
                {'name': 'Application Registry',  'url': '/portal/application-access/', 'icon': 'cil-applications'},
                {'name': 'Application Policies',  'url': '/portal/apps/', 'icon': 'cil-lock-locked'},
            ],
        },
        {
            'type': 'group',
            'name': 'Auth Trail',
            'icon': 'cil-history',
            'items': [
                {'name': 'Login Logs',      'url': '/portal/auth-trail/login-logs/',    'icon': 'cil-check-circle'},
                {'name': 'Failed Attempts', 'url': '/portal/auth-trail/failed-attempts/', 'icon': 'cil-warning'},
                {'name': 'Audit Log',       'url': '/portal/auth-trail/audit-log/',      'icon': 'cil-note'},
            ],
        },
    ]
    return {'nav_items': nav}