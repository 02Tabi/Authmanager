from django.db import migrations
import hmac
import hashlib
from django.conf import settings

def enforce_version_markers(apps, schema_editor):
    Application = apps.get_model('Middleware', 'Application')
    
    for app in Application.objects.all():
        if app.app_secret and not app.app_secret.startswith('hmac_sha256$'): 
            key = getattr(settings, 'APP_SECRET_HMAC_KEY', settings.SECRET_KEY).encode('utf-8')
            
            digest = hmac.new(
                key, 
                app.app_secret.encode('utf-8'), 
                hashlib.sha256
            ).hexdigest()
            
            app.app_secret = f"hmac_sha256${digest}"
            app.save(update_fields=['app_secret'])

class Migration(migrations.Migration):
    dependencies = [
        ('Middleware', '0024_alter_application_app_secret'), 
    ]

    operations = [
        migrations.RunPython(enforce_version_markers),
    ]