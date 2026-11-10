from celery import shared_task
from .notification_service import sms_helper 

@shared_task
def send_otp_async(phone_number, message):
    try:
        sms_helper(phone_number, message)
        return True
    except Exception as e:
        print(f"ASYNC SMS ERROR: {e}")
        return False