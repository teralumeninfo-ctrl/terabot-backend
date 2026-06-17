from django.urls import path
from . import views

urlpatterns = [
    path('chat/', views.chat, name='terabot-chat'),
    path('test-groq/', views.test_groq),
]
