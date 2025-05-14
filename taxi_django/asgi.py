import os
import django
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'taxi_django.settings')

# This line ensures that Django apps are loaded
django.setup()

application = get_asgi_application()

# Now import routing modules
import quick_chat.routing
import chat.routing

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                chat.routing.websocket_urlpatterns + quick_chat.routing.websocket_urlpatterns
            )
        )
    ),
})