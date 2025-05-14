from django.urls import path
from . import views

urlpatterns = [
    path('moving_taxi/', views.moving_taxi_view, name='moving_taxi_view'),
    path('api/taxi-location-json/', views.taxi_location_json, name='taxi_location_json'),  # JSON 데이터 엔드포인트
]
