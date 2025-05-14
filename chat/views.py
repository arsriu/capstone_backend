from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404, render
from .models import ChatRoom, ChatMessage
from signup.models import UserInfo
from .serializers import ChatRoomSerializer, ChatMessageSerializer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from uuid import UUID
import json
from django.http import JsonResponse
import logging
from datetime import datetime, timedelta, timezone
from dateutil import parser

logger = logging.getLogger(__name__)

# Define Korean Standard Time (KST) timezone
KST = timezone(timedelta(hours=9))

def generate_kakaopay_deeplink(base_link, amount_hex):
    return f"{base_link}{amount_hex}"

@api_view(['POST'])
def create_room(request):
    data = request.data
    user_id = data.get('user_id')
    user_name = data.get('user_name')
    original_departure_time = data.get('departure_time')

    logger.info(f"Create Room Request Received: {data}")

    if original_departure_time:
        try:
            departure_time = parser.parse(original_departure_time)
            stored_departure_time = departure_time + timedelta(hours=9)
            stored_departure_time = stored_departure_time.astimezone(timezone.utc)
        except ValueError:
            return Response({'error': 'Invalid date format'}, status=status.HTTP_400_BAD_REQUEST)

    data['departure_time'] = stored_departure_time
    serializer = ChatRoomSerializer(data=data)
    if serializer.is_valid():
        chat_room = serializer.save()
        chat_room.participants.append({'user_id': user_id, 'user_name': user_name, 'leader': True})
        chat_room.save()

        response_data = {
            'room_id': str(chat_room.room_id),
            'message': 'Room created and joined successfully.',
            'room_data': {
                'room_id': str(chat_room.room_id),
                'room_name': chat_room.room_name,
                'departure': chat_room.departure,
                'destination': chat_room.destination,
                'departure_time': departure_time.isoformat() if chat_room.departure_time else None,
                'participants': chat_room.participants,
            }
        }
        return Response(response_data, status=status.HTTP_201_CREATED)

    logger.error(f"Create Room Validation Error: {serializer.errors}")
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def get_chat_rooms(request):
    chat_rooms = ChatRoom.objects.filter(active=True)
    chat_rooms_data = []
    
    for room in chat_rooms:
        room_data = {
            'room_id': str(room.room_id),
            'room_name': room.room_name,
            'departure': room.departure,
            'destination': room.destination,
            'departure_time': room.departure_time.astimezone(KST).isoformat() if room.departure_time else None,
            'participants': room.participants,
            'recruitment_complete': room.recruitment_complete,
        }
        chat_rooms_data.append(room_data)
    
    return Response(chat_rooms_data)

@api_view(['GET'])
def get_chat_room_data(request, room_id):
    try:
        chat_room = ChatRoom.objects.get(room_id=room_id)
    except ChatRoom.DoesNotExist:
        return Response({'message': 'Room not found.'}, status=status.HTTP_404_NOT_FOUND)

    chat_messages = ChatMessage.objects.filter(room=chat_room).order_by('timestamp')
    if not chat_messages.exists():
        return Response({'message': 'No messages found for this room.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = ChatMessageSerializer(chat_messages, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK, content_type="application/json; charset=utf-8")

@api_view(['POST'])
def join_room(request, room_id):
    user_id = request.data.get('user_id')
    user_name = request.data.get('user_name')

    # Fetch the chat room
    chat_room = get_object_or_404(ChatRoom, room_id=room_id)

    # Check if recruitment is complete
    if chat_room.recruitment_complete:
        return Response({'message': 'Room recruitment is complete, no more participants can join'}, status=status.HTTP_403_FORBIDDEN)

    # Check if the room is full
    if len(chat_room.participants) >= 4:
        return Response({'message': 'Room is full'}, status=status.HTTP_403_FORBIDDEN)

    # Remove the user if already in the list to avoid duplicate entries
    chat_room.participants = [p for p in chat_room.participants if p['user_id'] != user_id]

    # Add the new participant as a non-leader
    chat_room.participants.append({'user_id': user_id, 'user_name': user_name, 'leader': False})
    
    # Assign the first participant as the leader if there is no leader
    if not any(p['leader'] for p in chat_room.participants):
        chat_room.participants[0]['leader'] = True

    # Save changes to the chat room
    chat_room.save()

    # Prepare response data with the updated room information
    response_data = {
        'message': 'Joined room successfully',
        'room_data': {
            'room_id': str(chat_room.room_id),
            'room_name': chat_room.room_name,
            'departure': chat_room.departure,
            'destination': chat_room.destination,
            'departure_time': chat_room.departure_time.astimezone(timezone.utc).isoformat() if chat_room.departure_time else None,
            'participants': chat_room.participants,
        }
    }

    return Response(response_data, status=status.HTTP_200_OK)

@api_view(['POST'])
def exit_room(request):
    room_id = request.data.get('room_id')
    user_id = request.data.get('user_id')

    # Fetch the chat room and user
    chat_room = get_object_or_404(ChatRoom, room_id=room_id)
    user = get_object_or_404(UserInfo, user_id=user_id)
    user_name = user.name

    # Check if the user leaving is the leader
    is_leader = any(p['leader'] for p in chat_room.participants if p['user_id'] == user_id)

    # Remove the user from participants list
    chat_room.participants = [p for p in chat_room.participants if p['user_id'] != user_id]

    # Reassign the leader if the current leader is leaving and there are remaining participants
    new_leader_name = None
    if is_leader and chat_room.participants:
        chat_room.participants[0]['leader'] = True
        new_leader_name = chat_room.participants[0]['user_name']

    # Save changes to the chat room
    chat_room.save()

    # Send a real-time update to the WebSocket group
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'chat_{room_id}',
            {
                'type': 'participants_update',
                'message': f"{user_name}님이 방을 나갔습니다.",
                'participants': chat_room.participants,
                'is_system_message': True
            }
        )
        logger.info("Sent participants_update to WebSocket group for room %s", room_id)

        # Notify about leader change if a new leader is assigned
        if new_leader_name:
            async_to_sync(channel_layer.group_send)(
                f'chat_{room_id}',
                {
                    'type': 'participants_update',
                    'message': f"{new_leader_name}님이 새로운 방장이 되었습니다.",
                    'participants': chat_room.participants,
                    'is_system_message': True
                }
            )
            logger.info("New leader %s assigned in room %s", new_leader_name, room_id)

    except Exception as e:
        logger.error("Failed to send participants_update to WebSocket: %s", str(e))

    # Structure the response data similar to join_room
    response_data = {
        'message': 'Exited room successfully',
        'room_data': {
            'room_id': str(chat_room.room_id),
            'room_name': chat_room.room_name,
            'departure': chat_room.departure,
            'destination': chat_room.destination,
            'departure_time': chat_room.departure_time.astimezone(timezone.utc).isoformat() if chat_room.departure_time else None,
            'participants': chat_room.participants,
        }
    }

    return Response(response_data, status=status.HTTP_200_OK)

@api_view(['POST'])
def complete_recruitment(request, room_id):
    user_id = request.data.get('user_id')
    chat_room = get_object_or_404(ChatRoom, room_id=room_id)
    leader = next((p for p in chat_room.participants if p['leader']), None)

    # Ensure there are at least 2 participants to complete recruitment
    if len(chat_room.participants) < 2:
        return Response(
            {'message': 'At least 2 participants are required to complete recruitment.'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Only the leader can complete recruitment
    if leader is None or leader['user_id'] != user_id:
        return Response(
            {'message': 'Only the leader can complete recruitment.'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Mark recruitment as complete and save to the database
    chat_room.recruitment_complete = True
    chat_room.final_participants = chat_room.participants.copy()  # Save current participants to final_participants
    chat_room.save()  # Ensure changes are saved immediately

    # Notify participants of recruitment completion via WebSocket
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'chat_{room_id}',
            {
                'type': 'recruitment_complete',
                'message': "모집이 완료되었습니다. 이제 나가기 버튼을 사용할 수 없습니다.",
                'block_exit': True
            }
        )
    except Exception as e:
        logger.error(f"Failed to send recruitment completion notification for room {room_id}: {e}")

    return Response({'message': 'Recruitment completed successfully'}, status=status.HTTP_200_OK)

@api_view(['POST'])
def settle_payment(request, room_id):
    user_id = request.data.get('user_id')
    total_amount = float(request.data.get('total_amount', 0))

    if not total_amount:
        return Response({'message': 'Total amount is required for settlement.'}, status=status.HTTP_400_BAD_REQUEST)

    chat_room = get_object_or_404(ChatRoom, room_id=room_id)
    user = get_object_or_404(UserInfo, user_id=user_id)

    # Check if recruitment has been completed
    if not chat_room.recruitment_complete:
        return Response({'message': 'Recruitment must be completed before settling payment.'}, status=status.HTTP_403_FORBIDDEN)

    participants_count = len(chat_room.participants)
    per_person_amount = total_amount / participants_count
    amount_hex = hex(int(per_person_amount * 524288)).upper().replace('0X', '')

    deeplink = f"{user.kakaopay_deeplink}{amount_hex}"

    # Mark settlement as complete in the database
    chat_room.settlement_complete = True
    chat_room.save()

    # Notify participants of settlement completion via WebSocket
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'chat_{room_id}',
        {
            'type': 'settlement_complete',
            'message': "정산이 완료되었습니다. 아래 링크로 결제 후 나가기를 진행해주세요.",
            'deeplink': deeplink,
            'per_person_amount': int(per_person_amount),
            'allow_exit': True
        }
    )

    return Response({
        'message': 'Settlement completed successfully',
        'deeplink': deeplink,
        'per_person_amount': int(per_person_amount),
    }, status=status.HTTP_200_OK)

@api_view(['GET'])
def get_room_participants(request, room_id):
    chat_room = get_object_or_404(ChatRoom, room_id=room_id)
    participants_info = [
        {
            'user_id': participant['user_id'],
            'user_name': participant['user_name'],
            'leader': participant['leader']
        }
        for participant in chat_room.participants
    ]

    return Response(participants_info, status=status.HTTP_200_OK)

@api_view(['GET'])
def get_final_participants(request, room_id):
    logger.info(f"Fetching final participants for room_id: {room_id}")

    # Retrieve the chat room if it exists
    try:
        chat_room = ChatRoom.objects.get(room_id=room_id)
    except ChatRoom.DoesNotExist:
        logger.warning(f"Room with id {room_id} not found.")
        return Response({'message': 'Room not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Log the recruitment_complete status
    logger.info(f"Recruitment complete status for room {room_id}: {chat_room.recruitment_complete}")

    # Check if recruitment is complete
    if not chat_room.recruitment_complete:
        logger.warning(f"Recruitment not completed for room {room_id}. Final participants are not available yet.")
        return Response({
            'message': 'Recruitment not completed yet. Final participants will be available after completion.'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Fetch and return final participants if recruitment is complete
    if not chat_room.final_participants:
        logger.warning(f"No final participants found for room {room_id}.")
        return Response({'message': 'No final participants found.'}, status=status.HTTP_404_NOT_FOUND)

    logger.info(f"Final participants for room {room_id}: {chat_room.final_participants}")
    return Response({
        'room_id': str(chat_room.room_id),
        'final_participants': chat_room.final_participants,
    }, status=status.HTTP_200_OK)

@api_view(['GET'])
def get_final_participants(request, room_id):
    chat_room = get_object_or_404(ChatRoom, room_id=room_id)
    # JSON으로 직렬화하며 ensure_ascii=False 설정 적용
    final_participants_json = json.dumps(chat_room.final_participants, ensure_ascii=False)
    return JsonResponse(
        {'final_participants': json.loads(final_participants_json)},
        status=status.HTTP_200_OK
    )

@api_view(['POST'])
def calculate_and_deeplink(request):
    try:
        room_id = request.data.get('room_id')
        user_id = request.data.get('user_id')
        total_amount = request.data.get('total_amount', 0)
        participants_count = request.data.get('participants_count', 1)
        
        per_person_amount = total_amount / participants_count
        amount_hex = hex(int(per_person_amount * 524288)).upper().replace('0X', '')

        deeplink = generate_kakaopay_deeplink(user_id, amount_hex)
        
        return Response({
            'deeplink': deeplink,
            'per_person_amount': int(per_person_amount),
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def leave_all_rooms(request, user_id):
    try:
        # 사용자가 참가 중인 모든 채팅방 가져오기
        chat_rooms = ChatRoom.objects.filter(participants__contains=[{'user_id': user_id}])
        
        for room in chat_rooms:
            # 사용자 제거
            room.participants = [p for p in room.participants if p['user_id'] != user_id]
            
            # 방장이 떠나면 새로운 방장 지정
            if not any(p['leader'] for p in room.participants) and room.participants:
                room.participants[0]['leader'] = True
            
            room.save()

        return Response({'message': 'Successfully left all chat rooms'}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error leaving all rooms: {str(e)}")
        return Response({'error': 'Failed to leave all rooms'}, status=status.HTTP_400_BAD_REQUEST)

def map_view(request):
    return render(request, 'map.html')
