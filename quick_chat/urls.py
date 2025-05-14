from django.urls import path
from .views import (
     quick_exit_room, match_or_create_room, quick_join_room,
    quickquick_exit_room,  calculate_and_deeplink, settlement_complete, get_quick_final_participants
)

app_name = 'quick_chat'

urlpatterns = [
    path('quick_exit_room/', quick_exit_room, name='quick_exit_room'),
    path('quick_join_room/<uuid:room_id>/', quick_join_room, name='quick_join_room'),
    path('match_or_create_room/', match_or_create_room, name='match_or_create_room'),
    path('quickquick_exit_room/', quickquick_exit_room, name='quickquick_exit_room'),
    path('calculate_and_deeplink/', calculate_and_deeplink, name='calculate_and_deeplink'),
    path('settlement_complete/', settlement_complete, name='settlement_complete'),
    path('get_final_participants/<str:room_id>/', get_quick_final_participants, name='get_quick_final_participants'),
]
