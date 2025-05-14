from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/quick_chat/(?P<room_id>[^/]+)/$', consumers.QuickChatConsumer.as_asgi()),
    re_path(r'ws/quickquick_chat/(?P<room_id>[^/]+)/$', consumers.QuickQuickChatConsumer.as_asgi()),
]
