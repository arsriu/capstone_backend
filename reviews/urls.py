from django.urls import path
from . import views

urlpatterns = [
    path('submit_ratings/', views.submit_ratings, name='submit_ratings'),
    path('quick_submit_ratings/', views.quick_submit_ratings, name='quick_submit_ratings'),
    path('average_rating/<str:reviewed_user_id>/', views.average_rating, name='average_rating'),
    ]
