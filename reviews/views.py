from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import ChatReview
from chat.models import ChatRoom
from .models import QuickChatReview
from quick_chat.models import QuickChatRoom, QuickQuickChatRoom
import logging
from django.apps import apps

logger = logging.getLogger(__name__)

@api_view(['POST'])
def submit_ratings(request):
    current_user_id = request.data.get('current_user_id')
    room_id = request.data.get('room_id')
    ratings = request.data.get('ratings', [])

    # Validate if room exists
    room = ChatRoom.objects.filter(room_id=room_id).first()
    if not room:
        return Response({'error': 'Room not found'}, status=status.HTTP_404_NOT_FOUND)

    # Get the final participants of the room
    final_participants = room.final_participants  # Adjust according to how you access final_participants

    # Check that all reviewed user IDs are valid participants
    valid_reviewed_user_ids = {p['user_id'] for p in final_participants}
    for rating in ratings:
        reviewed_user_id = rating['user_id']
        review_score = rating['rating']

        # Check if the user being reviewed is a valid participant
        if reviewed_user_id not in valid_reviewed_user_ids:
            return Response({'error': f'User {reviewed_user_id} is not a valid participant.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Create a review record for each rating
        ChatReview.objects.create(
            room=room,
            user_id=current_user_id,
            reviewed_user_id=reviewed_user_id,
            review_score=review_score
        )

    return Response({'message': 'Ratings submitted successfully'}, status=status.HTTP_200_OK)

@api_view(['POST'])
def quick_submit_ratings(request):
    try:
        logger.info(f"Received request data: {request.data}")
        room_id = request.data.get("room_id")
        current_user_id = request.data.get("current_user_id")
        ratings = request.data.get("ratings", [])

        # Get the QuickQuickChatRoom instance
        QuickQuickChatRoom = apps.get_model("quick_chat", "QuickQuickChatRoom")
        try:
            quickquick_room = QuickQuickChatRoom.objects.get(quickquick_room_id=room_id)
        except QuickQuickChatRoom.DoesNotExist:
            logger.error(f"QuickQuickChatRoom with id {room_id} not found.")
            return Response({"message": "Room not found."}, status=status.HTTP_404_NOT_FOUND)

        # Iterate over the ratings and save each review
        for rating in ratings:
            user_id = rating.get("user_id")
            review_score = rating.get("rating")

            if not user_id or review_score is None:
                continue  # Skip invalid data

            QuickChatReview = apps.get_model("reviews", "QuickChatReview")

            # Avoid duplicate reviews
            if QuickChatReview.objects.filter(
                room=quickquick_room, user_id=current_user_id, reviewed_user_id=user_id
            ).exists():
                logger.info(f"Duplicate review skipped for user {user_id}")
                continue

            # Save the review
            QuickChatReview.objects.create(
                room=quickquick_room,  # Ensure QuickQuickChatRoom instance is passed
                user_id=current_user_id,
                reviewed_user_id=user_id,
                review_score=review_score,
            )
            logger.info(f"Saved review for user {user_id} with score {review_score}")

        return Response({"message": "Reviews submitted successfully."}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error occurred: {str(e)}", exc_info=True)
        return Response({"message": "An error occurred while submitting reviews."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def average_rating(request, reviewed_user_id):
    try:
        # ChatReview에서 점수 가져오기
        chat_scores = ChatReview.objects.filter(reviewed_user_id=reviewed_user_id).values_list('review_score', flat=True)
        # QuickChatReview에서 점수 가져오기
        quick_chat_scores = QuickChatReview.objects.filter(reviewed_user_id=reviewed_user_id).values_list('review_score', flat=True)

        # 두 모델의 점수를 하나의 리스트로 병합
        all_scores = list(chat_scores) + list(quick_chat_scores)

        # 점수가 없을 경우 기본값 0.0 반환
        if not all_scores:
            return Response({'average_rating': 0.0}, status=200)

        # 총합 및 평균 계산
        total_score = sum(all_scores)
        average = round(total_score / len(all_scores), 2)

        return Response({'average_rating': average}, status=200)
    except Exception as e:
        return Response({'error': str(e)}, status=500)
