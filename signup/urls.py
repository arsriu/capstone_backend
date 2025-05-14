from django.urls import path
from .views import (
    get_user_info, 
    post_user_info, 
    crawl_user_info, 
    check_user_id, 
    login_user,
    get_user_info2  # 추가된 get_user_info2 뷰를 위한 경로
)

urlpatterns = [
    # 사용자 정보 조회 (get_user_info와 get_user_info2를 구분해서 추가)
    path('user/info/<str:user_id>/', get_user_info, name='get_user_info'),
    path('user/info2/<str:user_id>/', get_user_info2, name='get_user_info2'),
    
    # 사용자 정보 생성
    path('user/info/', post_user_info, name='post_user_info'),
    
    # 사용자 정보 크롤링
    path('user/crawl/', crawl_user_info, name='crawl_user_info'),
    
    # 사용자 ID 중복 확인
    path('user/check/<str:user_id>/', check_user_id, name='check_user_id'),
    
    # 로그인
    path('login/', login_user, name='login_user'),
]
