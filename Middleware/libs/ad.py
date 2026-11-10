import ssl
import logging
from django.conf import settings
from ldap3 import Server, Connection, ALL, NTLM, Tls

logger = logging.getLogger(__name__)

def authenticate_user(username, password):
    try:
        cert_policy = ssl.CERT_REQUIRED if settings.AD_REQUIRE_CERT else ssl.CERT_NONE
        
        tls_config = Tls(validate=cert_policy, version=ssl.PROTOCOL_TLSv1_2)
        
        server = Server(
            settings.AD_SERVER_HOST, 
            port=636, 
            use_ssl=True, 
            tls=tls_config, 
            get_info=ALL
        )
        
        conn = Connection(
            server,
            user=f"PRUDENTIALBANK\\{username}",
            password=password,
            authentication=NTLM,
            auto_bind=True,
        )
        
        if conn.bound:
            return True
        return False

    except Exception:
        logger.error(f"Active Directory authentication failed for user: {username}")
        return False