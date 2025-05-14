from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import QuickQuickChatRoom 
from asgiref.sync import async_to_sync
from .models import QuickChatRoom
from signup.models import UserInfo
from channels.layers import get_channel_layer
from django.apps import apps
import json
import logging

logger = logging.getLogger(__name__)
# Helper function: Update participants in a room
def update_participants(room, user_id, user_name=None, action="add"):
    """Add or remove participants in a room."""
    if action == "add" and user_id not in [p['user_id'] for p in room.quick_participants]:
        room.quick_participants.append({'user_id': user_id, 'user_name': user_name, 'ready': False})
    elif action == "remove":
        room.quick_participants = [p for p in room.quick_participants if p['user_id'] != user_id]
    room.save()

# Helper function: Generate KakaoPay deeplink
def generate_kakaopay_deeplink(base_link, amount_hex):
    """Generate a KakaoPay deeplink using base link and amount in hex."""
    return f"{base_link}{amount_hex}"

# Helper function: Finalize recruitment if conditions are met
def finalize_recruitment_if_needed(room):
    """Finalize recruitment if the required conditions are met."""
    if len(room.quick_participants) >= 4 and all(p['ready'] for p in room.quick_participants):
        room.quick_recruitment_complete = True
        room.quick_final_participants = room.quick_participants.copy()
        room.save()
        logger.info(f"Room {room.quick_room_id} recruitment complete.")
        return True
    return False

# Helper function: Reset timer for a room
def reset_timer(room):
    """Reset the room's timer to 30 seconds."""
    room.quick_timer_started = False
    room.save()

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'quick_chat_{room.quick_room_id}',
        {
            'type': 'timer_reset',
            'message': 'Timer has been reset to 30 seconds.',
            'countdown': 30
        }
    )
    logger.info(f"Timer reset for room {room.quick_room_id}.")

# Helper function: Delete an empty room
def delete_empty_room(room):
    """Delete a room if it has no participants."""
    logger.info(f"Deleting room {room.quick_room_id} as it is empty.")
    room.delete()

# Match or create a new chat room
@csrf_exempt
def match_or_create_room(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)

    try:
        data = json.loads(request.body)
        departure = data.get('departure')
        destination = data.get('destination')
        user_id = data.get('user_id')
        user_name = data.get('user_name', None)

        if not departure or not destination or not user_id:
            logger.error("Missing required fields in match_or_create_room")
            return JsonResponse({'error': 'Missing required fields'}, status=400)

        if not user_name:
            user_name = get_object_or_404(UserInfo, user_id=user_id).name

        channel_layer = get_channel_layer()

        # Find an available room or create a new one
        available_room = QuickChatRoom.objects.filter(
            quick_departure=departure,
            quick_destination=destination,
            quick_recruitment_complete=False
        ).first()

        if available_room:
            room = available_room
            created = False
        else:
            # Create a new room if no available room exists
            room = QuickChatRoom.objects.create(
                quick_departure=departure,
                quick_destination=destination,
                quick_room_name=f'{departure} - {destination}'
            )
            created = True
            logger.info(f"Created new room: {room.quick_room_id}")

        # Add user to the room if not already present
        update_participants(room, user_id, user_name, action="add")
        logger.info(f"User {user_id} joined room {room.quick_room_id}")

        # Notify WebSocket group about the new participant
        async_to_sync(channel_layer.group_send)(
            f'quick_chat_{room.quick_room_id}',
            {
                'type': 'participants_update',
                'message': f'{user_name} has joined the room.',
                'participants': room.quick_participants
            }
        )

        # Finalize recruitment if conditions are met
        if finalize_recruitment_if_needed(room):
            async_to_sync(channel_layer.group_send)(
                f'quick_chat_{room.quick_room_id}',
                {
                    'type': 'recruitment_complete',
                    'message': 'Recruitment is complete.',
                }
            )

        user = get_object_or_404(UserInfo, user_id=user_id)
        return JsonResponse({
            'room_id': str(room.quick_room_id),
            'participants': room.quick_participants,
            'kakaopay_deeplink': user.kakaopay_deeplink,
            'created': created,  # Indicate if a new room was created
        })

    except json.JSONDecodeError:
        logger.error("Invalid JSON data in match_or_create_room")
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Unexpected error in match_or_create_room: {e}", exc_info=True)
        return JsonResponse({'error': 'An unexpected error occurred'}, status=500)

# Quick join room
@csrf_exempt
def quick_join_room(request, room_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)

    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        user_name = data.get('user_name', None)

        room = get_object_or_404(QuickChatRoom, quick_room_id=room_id)

        if room.quick_recruitment_complete:
            logger.info(f"User {user_id} attempted to join completed room {room_id}")
            return JsonResponse({'error': 'Room recruitment is complete'}, status=403)

        if not user_name:
            user_name = get_object_or_404(UserInfo, user_id=user_id).name

        update_participants(room, user_id, user_name, action="add")

        finalize_recruitment_if_needed(room)

        user = get_object_or_404(UserInfo, user_id=user_id)
        return JsonResponse({
            'participants': room.quick_participants,
            'kakaopay_deeplink': user.kakaopay_deeplink
        })

    except QuickChatRoom.DoesNotExist:
        return JsonResponse({'error': 'Room not found'}, status=404)
    except json.JSONDecodeError:
        logger.error("Invalid JSON data in quick_join_room")
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Failed to join room {room_id}: {e}", exc_info=True)
        return JsonResponse({'error': f"Failed to join room: {e}"}, status=400)

@csrf_exempt
def quick_exit_room(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)

    try:
        data = json.loads(request.body)
        room_id = data.get('room_id')
        user_id = data.get('user_id')

        if not room_id or not user_id:
            return JsonResponse({'error': 'Missing room_id or user_id'}, status=400)

        # 방 존재 여부 확인
        try:
            room = QuickChatRoom.objects.get(quick_room_id=room_id)
        except QuickChatRoom.DoesNotExist:
            logger.warning(f"Room {room_id} does not exist. Skipping.")
            return JsonResponse({'status': 'room_already_deleted'})

        # 참가자 제거 (이미 나갔는지 확인)
        if user_id not in [p["user_id"] for p in room.quick_participants]:
            logger.info(f"User {user_id} already left room {room_id}. Skipping.")
            return JsonResponse({'status': 'user_already_left'})

        room.quick_participants = [
            p for p in room.quick_participants if p["user_id"] != user_id
        ]
        room.save()

        logger.info(f"User {user_id} left room {room_id}. Remaining participants: {len(room.quick_participants)}")

        # 남은 참가자 수에 따른 추가 처리
        if len(room.quick_participants) == 0:
            logger.info(f"Deleting room {room_id} as it is empty.")
            room.delete()
            return JsonResponse({'status': 'room_deleted'})

        if len(room.quick_participants) == 1:
            logger.info(f"Resetting timer for room {room_id} as only one participant remains.")
            # 타이머 리셋 메시지 전송
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"quick_chat_{room_id}",
                {"type": "timer_reset", "countdown": 30, "message": "Timer has been reset to 30 seconds."}
            )

        return JsonResponse({'status': 'left', 'participants': room.quick_participants})

    except json.JSONDecodeError:
        logger.error("Invalid JSON data in quick_exit_room")
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Failed to exit room {room_id}: {str(e)}", exc_info=True)
        return JsonResponse({'error': f"Failed to exit room: {str(e)}"}, status=400)

@api_view(['POST'])
def calculate_and_deeplink(request):
    try:
        room_id = request.data.get('room_id')
        user_id = request.data.get('user_id')
        total_amount = Decimal(request.data.get('total_amount'))
        participants_count = int(request.data.get('participants_count'))

        # Calculate per-person amount
        per_person_amount = total_amount / Decimal(participants_count)
        amount_hex = hex(int(per_person_amount * 524288)).upper().replace('0X', '')

        # Retrieve the initiating user's KakaoPay deeplink base URL
        user = get_object_or_404(UserInfo, user_id=user_id)
        deeplink = generate_kakaopay_deeplink(user.kakaopay_deeplink, amount_hex)

        # Update the room's settlement status
        room = get_object_or_404(QuickQuickChatRoom, quickquick_room_id=room_id)
        room.quickquick_is_settled = False  # Initially set to False
        room.quickquick_final_participants_saved = True  # Mark final participants as saved
        room.quickquick_final_participants = room.quickquick_participants.copy()  # Save final participants
        logger.info(f"Before saving: quickquick_is_settled={room.quickquick_is_settled}")

        # Save changes to the room
        room.save()
        room.refresh_from_db()  # Refresh the room instance to verify saved state
        logger.info(f"After saving: quickquick_is_settled={room.quickquick_is_settled}")

        # Confirm that quickquick_is_settled is set to False after saving
        if room.quickquick_is_settled:
            logger.warning(f"Failed to set quickquick_is_settled to False for room {room_id}")

        # Send the deeplink to all participants through WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'quickquick_chat_{room_id}',
            {
                'type': 'settlement_complete',
                'deeplink': deeplink,
                'message': f"1인금액: {int(per_person_amount)}원. 링크를 클릭해주세요."
            }
        )

        # Update quickquick_is_settled to True to mark settlement as complete
        room.quickquick_is_settled = True
        room.save()
        logger.info(f"Settlement complete: quickquick_is_settled={room.quickquick_is_settled} for room {room_id}")

        return Response({
            'deeplink': deeplink,
            'per_person_amount': int(per_person_amount),
            'message': 'Settlement message sent to participants.'
        }, status=200)

    except Exception as e:
        logger.error(f"Error in calculate_and_deeplink: {str(e)}")
        return Response({'error': str(e)}, status=400)

@csrf_exempt
def settlement_complete(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            room_id = data.get('room_id')

            # Retrieve the QuickQuickChatRoom
            quickquick_room = QuickQuickChatRoom.objects.filter(quickquick_room_id=room_id).first()
            if quickquick_room:
                quickquick_room.quickquick_is_settled = True  # Mark settlement as complete
                quickquick_room.save()
                logger.info(f"QuickQuickChatRoom {room_id} settlement marked as complete.")

                # Notify participants via WebSocket
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f'quickquick_chat_{room_id}',  # WebSocket group name
                    {
                        'type': 'settlement_completed',
                        'message': 'Settlement has been completed. You can now exit the room.'
                    }
                )

                return JsonResponse({'status': 'success', 'message': 'Settlement marked as complete.'})
            else:
                logger.warning(f"QuickQuickChatRoom {room_id} not found. Settlement flag not updated.")
                return JsonResponse({'status': 'error', 'message': 'Room not found.'}, status=404)

        except Exception as e:
            logger.error(f"Error while marking settlement complete for room {room_id}: {str(e)}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@csrf_exempt
def quickquick_exit_room(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            room_id = data.get('room_id')
            user_id = data.get('user_id')

            # Validate input data
            if not room_id or not user_id:
                return JsonResponse({'error': 'Missing room_id or user_id in the request.'}, status=400)

            # Retrieve the QuickQuickChatRoom
            try:
                room = QuickQuickChatRoom.objects.get(quickquick_room_id=room_id)
                logger.info(f"Room found: quickquick_is_settled={room.quickquick_is_settled}, quickquick_is_active={room.quickquick_is_active}")
            except QuickQuickChatRoom.DoesNotExist:
                logger.warning(f"Room {room_id} not found.")
                return JsonResponse({'error': 'Room does not exist.'}, status=404)

            # Check if the room is active
            if not room.quickquick_is_active:
                logger.warning(f"Room {room_id} is inactive.")
                return JsonResponse({'error': 'Room is inactive.'}, status=403)

            # Allow exit only if settlement is complete
            if not room.quickquick_is_settled:
                logger.warning(f"User {user_id} attempted to exit room {room_id} before settlement was completed.")
                return JsonResponse({'error': 'Settlement not completed. Cannot exit the room.'}, status=403)

            # Check if the user exists in participants
            current_participants = room.quickquick_participants or []
            if not any(p['user_id'] == user_id for p in current_participants):
                logger.warning(f"User {user_id} not found in participants of room {room_id}.")
                return JsonResponse({'error': 'User not found in room participants.'}, status=404)

            # Prepare review participants excluding the exiting user
            final_participants = room.quickquick_final_participants or []
            review_participants = [
                participant for participant in final_participants if participant['user_id'] != user_id
            ]

            # Remove the user from the active participants
            updated_participants = [
                participant for participant in current_participants if participant['user_id'] != user_id
            ]
            room.quickquick_participants = updated_participants
            room.quickquick_participant_count = len(updated_participants)
            room.save()

            # Notify other participants about the user’s departure
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'quickquick_chat_{room_id}',
                {
                    'type': 'participants_update',
                    'message': f'User {user_id} has left the room.',
                    'participants': updated_participants,
                }
            )

            logger.info(f"User {user_id} successfully left room {room_id}. Remaining participants: {updated_participants}")

            # Return review participants and room data for navigation to the review page
            return JsonResponse({
                'status': 'left',
                'review_participants': review_participants,
                'room_details': {
                    'departure': room.quickquick_departure,
                    'destination': room.quickquick_destination,
                    'departure_time': room.quickquick_departure_time,
                },
            }, status=200)

        except Exception as e:
            logger.error(f"Failed to process exit for room {room_id}: {str(e)}", exc_info=True)
            return JsonResponse({'error': 'An internal server error occurred.'}, status=500)

    logger.warning("Invalid request method for quickquick_exit_room.")
    return JsonResponse({'error': 'Invalid request method.'}, status=405)


@api_view(['GET'])
def get_quick_final_participants(request, room_id):
    logger.info(f"Fetching final participants for QuickQuickMatch room_id: {room_id}")

    # Retrieve the QuickQuickChatRoom if it exists
    try:
        quickquick_chat_room = QuickQuickChatRoom.objects.get(quickquick_room_id=room_id)  # 필드명 확인
    except QuickQuickChatRoom.DoesNotExist:
        logger.warning(f"QuickQuickMatch room with id {room_id} not found.")
        return Response({'message': 'Room not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Check and log recruitment completion status
    recruitment_complete = quickquick_chat_room.quickquick_recruitment_complete
    logger.info(f"Recruitment complete status for QuickQuickMatch room {room_id}: {recruitment_complete}")

    # Check if recruitment is complete
    if not recruitment_complete:
        logger.warning(f"Recruitment not completed for QuickQuickMatch room {room_id}. Final participants are not available yet.")
        return Response({
            'message': 'Recruitment not completed yet. Final participants will be available after completion.'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Fetch and return final participants
    final_participants = quickquick_chat_room.quickquick_final_participants
    if not final_participants:
        logger.warning(f"No final participants found for QuickQuickMatch room {room_id}.")
        return Response({'message': 'No final participants found.'}, status=status.HTTP_404_NOT_FOUND)

    # Ensure participants are in the correct format
    if not isinstance(final_participants, list):
        logger.error(f"Final participants for QuickQuickMatch room {room_id} are not in the correct format.")
        return Response({'message': 'Final participants are in an invalid format.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Log and return final participants
    logger.info(f"Final participants for QuickQuickMatch room {room_id}: {final_participants}")
    return Response({
        'room_id': str(quickquick_chat_room.quickquick_room_id),
        'final_participants': final_participants,
    }, status=status.HTTP_200_OK)
