from django.urls import path
from .views import alive_view,RetrieveInfoView

urlpatterns = [
    path('isalive/', alive_view, name='alive-view'), 
     path('retieve_info/', RetrieveInfoView.as_view(), name='retrieve-info'), 
]
