from django.urls import path
from .views import chat_page, chat, upload_image, chat_history

urlpatterns = [
    path('chat/', chat_page, name='chat'),
    path('chat/send/', chat, name='chat_send'),
    path('upload/', upload_image, name='upload_image'),
    path('history/', chat_history, name='chat_history'),
]
