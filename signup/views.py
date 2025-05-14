from django.shortcuts import render, get_object_or_404
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.decorators import api_view, parser_classes
from .models import UserInfo
from .serializers import UserInfoSerializers
from .crawl import Crawl, CustomException
from django.http import JsonResponse
from django.contrib.auth.hashers import make_password, check_password
import logging

logger = logging.getLogger(__name__)

@api_view(['POST'])
@parser_classes([JSONParser])
def crawl_user_info(request):
    user_id = request.data.get('user_id')
    password = request.data.get('password')

    logger.info(f"Received crawl request for user_id: {user_id}")

    if not user_id or not password:
        logger.warning("Missing user_id or password in request")
        return Response({"message": "user_id and password are required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        crawler = Crawl(user_id, password)
        user_info = crawler.crawl_user()
        logger.info(f"Crawled user info: {user_info}")
        return Response(user_info, status=status.HTTP_200_OK, content_type='application/json; charset=utf-8')
    except CustomException as e:
        logger.error(f"CustomException: {e.message}")
        return Response({"message": e.message}, status=e.code)
    except Exception as e:
        logger.error(f"Exception: {str(e)}")
        return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@parser_classes([JSONParser])
def post_user_info(request):
    data = request.data
    data['password'] = make_password(data['password'])  # 비밀번호를 해시화

    serializer = UserInfoSerializers(data=data)
    if serializer.is_valid():
        serializer.save()
        return Response({"message": "User information created successfully."}, 
                        status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def check_user_id(request, user_id):
    try:
        user = UserInfo.objects.get(user_id=user_id)
        return Response({"message": "User ID already exists."}, status=status.HTTP_200_OK)
    except UserInfo.DoesNotExist:
        return Response({"message": "User ID is available."}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error checking user ID: {e}")
        return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@parser_classes([JSONParser])
def login_user(request):
    user_id = request.data.get('user_id')
    password = request.data.get('password')

    if not user_id or not password:
        return Response({'message': 'user_id and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = UserInfo.objects.get(user_id=user_id)
        if check_password(password, user.password):  # 비밀번호 해시 검증
            return Response({'message': 'Login successful', 'user_name': user.name}, status=status.HTTP_200_OK)
        else:
            return Response({'message': 'Invalid Credentials'}, status=status.HTTP_401_UNAUTHORIZED)
    except UserInfo.DoesNotExist:
        return Response({'message': 'Invalid Credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        
@api_view(['GET'])
def get_user_info(request, user_id):
    user = get_object_or_404(UserInfo, user_id=user_id)
    data = {
        'user_id': user.user_id,
        'user_name': user.name,
        'kakaopay_deeplink': user.kakaopay_deeplink
    }
    return JsonResponse(data, json_dumps_params={'ensure_ascii': False})
    
@api_view(['GET'])
def get_user_info2(request, user_id):
    try:
        # UserInfo 모델에서 user_id로 사용자 정보 가져오기
        user = get_object_or_404(UserInfo, user_id=user_id)
        
        # 사용자 정보 데이터 구성
        data = {
            'user_id': user.user_id,
            'user_name': user.name,
            'kakaopay_deeplink': user.kakaopay_deeplink,
        }
        
        # 성공적으로 데이터 반환
        return JsonResponse(data, json_dumps_params={'ensure_ascii': False}, status=200)
    
    except UserInfo.DoesNotExist:
        # 사용자 정보가 없을 경우 404 반환
        return Response({'error': 'User not found'}, status=404)
    
    except Exception as e:
        # 기타 예외 발생 시 500 오류 반환
        return Response({'error': str(e)}, status=500)

