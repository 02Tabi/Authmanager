import os
import sys
import django
import logging
import time
from django.utils import timezone
from django.apps import apps
from django.core import signing

BASE_DIR = "/var/www/AuthManager/Auth"  
sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings") 
django.setup()

import requests
import json

logger = logging.getLogger("auth_provisioning_monitor")

if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

logger.setLevel(logging.INFO)

Profile = apps.get_model("Middleware", "Profile") 
Permission = apps.get_model("Middleware", "Permission") 

BASE_ACTIVATION_URL = os.environ.get("AUTH_MANAGER_BASE_URL", "http://10.170.1.47")
CREDENTIAL_LINK_SALT = "app-credential-activation"
CREDENTIAL_LINK_MAX_AGE = 60 * 60 * 24  


def sms_helper(phone, content):
    """Sends SMS via Nalo Solutions."""
    url = "https://sms.nalosolutions.com/smsbackend/Resl_Prud/send-message/"
    if not phone:
        return None

    try:
        phone = str(phone)
        if phone.startswith("233"):
            phone = "0" + phone[3:]

        payload = {
            "username": "prudentialbankgh",
            "password": "Prudentialbankgh@2022",  
            "type": 0,
            "message": content,
            "destination": phone,
            "source": "PRUDENTIAL",
            "dlr": 1,
        }

        res = requests.get(url, params=payload, timeout=15)
        return {
            "err_code": res.status_code,
            "err_desc": res.reason,
            "content": res.content
        }
    except Exception as e:
        logger.error(f"SMS ERROR: {e}")
        return None

def mail_helper(cust_email, content):
    """Sends Email via Nalo Solutions."""
    url = "https://email.nalosolutions.com/smsbackend/clientapi/Resl_Prud/send-email/"
    if not cust_email:
        return None

    try:
        payload = json.dumps({
            "username": "prudentialbankgh",
            "password": "Prudentialbankgh@2022",  
            "emailTo": [cust_email],
            "emailFrom": "alert@prudentialbank.com.gh",
            "emailBody": content,
            "senderName": "Prudential Bank Ltd",
            "subject": "AUTH MANAGER - SET YOUR APP PASSWORD",
            "callBackUrl": "",
        })

        headers = {"Content-Type": "application/json"}
        email_response = requests.request(
            "POST", url, headers=headers, data=payload, verify=False, timeout=15
        )

        return {
            "status_code": email_response.status_code,
            "response": email_response.text
        }
    except Exception as e:
        logger.error(f"EMAIL ERROR: {e}")
        return None


def process_pending_local_users():
    """Finds newly assigned applications for local users and dispatches single-use activation links."""
    
    pending_permissions = Permission.objects.filter(
        approval_status='approved',
        credentials_sent=False
    )

    for perm in pending_permissions:
        user = perm.user
        
        if not user or not user.username:
            continue

        try:
            profile = Profile.objects.get(username=user)
        except Profile.DoesNotExist:
            continue

        # Corrected to include Hybrid users
        if profile.auth_type not in ["DB", "Hybrid"]:
            continue

        placeholder = signing.dumps({"perm_id": perm.id, "purpose": "placeholder"})
        perm.set_password(placeholder)

        app_name = perm.application.app_name if perm.application else "a new application"
        full_name = f"{profile.firstname or ''} {profile.lastname or ''}".strip() or user.username

        token = signing.dumps({"perm_id": perm.id}, salt=CREDENTIAL_LINK_SALT)
        activation_link = f"{BASE_ACTIVATION_URL}/portal/activate-credentials/{token}/"

        message = (
            f"Dear {full_name},\n\n"
            f"You have been granted access to {app_name} on Auth Manager. "
            f"Set your password for this application using the link below. "
            f"This link is single-use and expires in 24 hours:\n\n"
            f"{activation_link}\n\n"
            f"Application: {app_name}\n"
            f"Username: {user.username}\n\n"
            f"Thank you,\nPrudential Bank Ltd."
        )

        phone = profile.phone
        email = profile.email

        logger.info(f"Dispatching {app_name} activation link for user: {user.username} -> Phone: {phone} | Email: {email}")

        sms_helper(phone, message)
        mail_helper(email, message)

        perm.credentials_sent = True
        perm.save()

        logger.info(f"[ACTIVATION LINK SENT] Username: {user.username} | App: {app_name}")


def main_loop():
    logger.info("===== AUTH MANAGER ISOLATED CREDENTIAL DISPATCH SERVICE STARTED =====")

    while True:
        try:
            process_pending_local_users()
        except Exception as e:
            logger.exception(f"ERROR IN PROCESS CYCLE: {e}")

        time.sleep(2)

if __name__ == "__main__":
    main_loop()