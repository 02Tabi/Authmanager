import logging
import requests
import json

logger = logging.getLogger("auth_provisioning_monitor")


def sms_helper(phone, content):
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
        return {"err_code": res.status_code, "err_desc": res.reason, "content": res.content}
    except Exception as e:
        logger.error(f"SMS ERROR: {e}")
        return None


def mail_helper(cust_email, content, subject="AUTH MANAGER - YOUR NEW APP CREDENTIALS"):
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
            "subject": subject,
            "callBackUrl": "",
        })
        headers = {"Content-Type": "application/json"}
        res = requests.request("POST", url, headers=headers, data=payload, verify=False, timeout=15)
        return {"status_code": res.status_code, "response": res.text}
    except Exception as e:
        logger.error(f"EMAIL ERROR: {e}")
        return None
