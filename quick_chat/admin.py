from django.contrib import admin
from .models import QuickChatRoom, QuickChatMessage

admin.site.register(QuickChatRoom)
admin.site.register(QuickChatMessage)
