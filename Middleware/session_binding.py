import logging
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.conf import settings 

logger = logging.getLogger(__name__)

class SessionBindingMiddleware:
    """
    Binds the session to the browser's User-Agent.
    Kills the session if it is moved to a different browser type.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            current_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
            session_agent = request.session.get('bound_agent')

            if not session_agent:
                request.session['bound_agent'] = current_agent
            elif session_agent != current_agent:
                logger.warning(
                    f"SECURITY ALERT: Session Hijack Blocked. "
                    f"User: {request.user.username} | "
                    f"Expected: {session_agent} | "
                    f"Intruder: {current_agent}"
                )
                logout(request)
                
                return redirect('/portal/login/') 

        return self.get_response(request)