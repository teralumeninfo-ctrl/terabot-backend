from django.urls import path, include
from django.http import HttpResponse

def health(request):
    return HttpResponse("OK", status=200)

urlpatterns = [
    path('health/', health),
    path('api/chatbot/', include('chatbot.urls')),
]
