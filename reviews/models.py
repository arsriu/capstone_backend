from django.db import models
from uuid import uuid4
from chat.models import ChatRoom 
from quick_chat.models import QuickQuickChatRoom 

class ChatReview(models.Model):
    review_id = models.UUIDField(default=uuid4, primary_key=True, editable=False)
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='reviews')
    user_id = models.CharField(max_length=100)  
    reviewed_user_id = models.CharField(max_length=100)  
    review_score = models.PositiveSmallIntegerField()  
    review_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Review by {self.user_id} for {self.reviewed_user_id} in room {self.room.room_id}'
    

class QuickChatReview(models.Model):
    review_id = models.UUIDField(default=uuid4, primary_key=True, editable=False)
    room = models.ForeignKey(QuickQuickChatRoom, on_delete=models.CASCADE, related_name='reviews')
    user_id = models.CharField(max_length=100)  
    reviewed_user_id = models.CharField(max_length=100)  
    review_score = models.PositiveSmallIntegerField()  
    review_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Review by {self.user_id} for {self.reviewed_user_id} in room {self.room.room_id}'
