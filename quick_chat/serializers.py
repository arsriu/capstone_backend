from rest_framework import serializers
from .models import QuickChatRoom, QuickQuickChatRoom

# QuickChatRoom Serializer
class QuickChatRoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuickChatRoom
        fields = ['quick_room_id', 'quick_room_name', 'quick_departure', 'quick_destination', 'quick_participants']

# QuickQuickChatRoom Serializer
class QuickQuickChatRoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuickQuickChatRoom
        fields = ['quickquick_room_id', 'quickquick_room_name', 'quickquick_departure', 'quickquick_destination', 'quickquick_participants']
