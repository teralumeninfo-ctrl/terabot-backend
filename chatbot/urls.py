from django.urls import path
from . import views

urlpatterns = [
    path('chat/', views.chat, name='terabot-chat'),
    path('ping/', views.ping, name='terabot-ping'),
]
