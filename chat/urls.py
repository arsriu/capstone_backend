from django.urls import path
from .views import (
    join_room, create_room, exit_room, complete_recruitment, settle_payment,
    get_room_participants, get_chat_room_data, get_chat_rooms, map_view,
    calculate_and_deeplink, get_final_participants, leave_all_rooms
)

app_name = 'chat'

urlpatterns = [
    path('join_room/<uuid:room_id>/', join_room, name='join_room'),  # 특정 채팅방에 참가
    path('create_room/', create_room, name='create_room'),  # 새로운 채팅방 생성
    path('exit_room/', exit_room, name='exit_room'),  # 채팅방 나가기
    path('complete_recruitment/<uuid:room_id>/', complete_recruitment, name='complete_recruitment'),  # 모집 완료 처리
    path('settle_payment/<uuid:room_id>/', settle_payment, name='settle_payment'),  # 정산 처리
    path('room_participants/<uuid:room_id>/', get_room_participants, name='get_room_participants'),  # 특정 채팅방의 참가자 정보 가져오기
    path('room_data/<uuid:room_id>/', get_chat_room_data, name='get_chat_room_data'),  # 특정 채팅방의 데이터/메시지 가져오기
    path('get_chat_rooms/', get_chat_rooms, name='get_chat_rooms'),  # 모든 활성화된 채팅방 가져오기
    path('calculate_and_deeplink/', calculate_and_deeplink, name='calculate_and_deeplink'),  # 결제 금액 계산 및 링크 생성
    path('map/', map_view, name='map_view'),  # 지도 보기 렌더링
    path('get_final_participants/<uuid:room_id>/', get_final_participants, name='get_final_participants'),  # 모집 완료된 참가자 정보 가져오기
    path('leave_all/<str:user_id>/', leave_all_rooms, name='leave_all_rooms'),  # 모든 채팅방 나가기
]
