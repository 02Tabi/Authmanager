from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from Middleware.views import application_access, edit_app 

urlpatterns = [
    path('Tabi/', admin.site.urls),
    path('api/',     include('Middleware.urls')),       
    path('portal/',  include('Middleware.dashboard_urls')), 
    
    path('portal/application-access/', application_access, name='application_access'),
    path('portal/edit-app/<int:app_id>/', edit_app, name='edit_app'),
    
    path('', RedirectView.as_view(url='/portal/login/')), 
]