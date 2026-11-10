from django.db import migrations
import hmac
import hashlib
from django.conf import settings

def hash_legacy_secrets(apps, schema_editor):
    Application = apps.get_model('Middleware', 'Application')
    
    for app in Application.objects.all():
        if app.app_secret and len(app.app_secret) != 64: 
            # Fetch the key exactly as your models.py does
            key = getattr(settings, 'APP_SECRET_HMAC_KEY', settings.SECRET_KEY).encode('utf-8')
            
            hashed_secret = hmac.new(
                key, 
                app.app_secret.encode('utf-8'), 
                hashlib.sha256
            ).hexdigest()
            
            app.app_secret = hashed_secret
            app.save(update_fields=['app_secret'])

class Migration(migrations.Migration):
    dependencies = [
        ('Middleware', '0022_otptoken'), 
    ]

    operations = [
        migrations.RunPython(hash_legacy_secrets),
    ]