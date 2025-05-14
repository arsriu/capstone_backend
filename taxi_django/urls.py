from django.contrib import admin
from django.urls import path, include
from .views import main_page_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('my/', include('signup.urls')),
    path('chat/', include('chat.urls')),
    path('quick_chat/', include('quick_chat.urls', namespace='quick_chat')),
    path('taxi/', include('taxi.urls')),
    path('reviews/', include('reviews.urls')),
    path('', main_page_view, name='main_page'),
]