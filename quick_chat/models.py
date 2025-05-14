from django.db import models
import uuid
from datetime import datetime

# QuickChatRoom for quick_match_chat_page.dart
class QuickChatRoom(models.Model):
    quick_room_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    quick_room_name = models.CharField(max_length=100, default='default_room_name')
    quick_created_at = models.DateTimeField(auto_now_add=True)
    quick_updated_at = models.DateTimeField(auto_now=True)  # 최근 업데이트 시간 추가
    quick_participants = models.JSONField(default=list)
    quick_final_participants = models.JSONField(default=list, blank=True)
    quick_final_participants_saved = models.BooleanField(default=False)
    quick_participant_count = models.IntegerField(default=0)
    quick_departure = models.CharField(max_length=255, default='default_departure')
    quick_destination = models.CharField(max_length=255, default='default_destination')
    quick_departure_time = models.DateTimeField(null=True, blank=True)
    quick_recruitment_complete = models.BooleanField(default=False)
    quick_is_active = models.BooleanField(default=True)
    quick_is_settled = models.BooleanField(default=False)
    quick_timer_started = models.BooleanField(default=False)
    quick_max_participants = models.IntegerField(default=4)  # 최대 참가자 수 추가
    quick_min_participants = models.IntegerField(default=2)  # 최소 참가자 수 추가

    class Meta:
        ordering = ['-quick_created_at']  # 최신 생성 순으로 정렬
        verbose_name = 'Quick Chat Room'
        verbose_name_plural = 'Quick Chat Rooms'

    def __str__(self):
        return f"{self.quick_room_name} (ID: {self.quick_room_id})"

    def is_room_full(self):
        """Check if the room is full based on the maximum participant limit."""
        return len(self.quick_participants) >= self.quick_max_participants

    def add_participant(self, user_id, user_name):
        """Add a new participant to the room."""
        if not self.is_room_full():
            self.quick_participants.append({
                'user_id': user_id,
                'user_name': user_name,
                'ready': False
            })
            self.save()
        else:
            raise ValueError("Room is full. Cannot add more participants.")

    def remove_participant(self, user_id):
        """Remove a participant from the room."""
        self.quick_participants = [p for p in self.quick_participants if p['user_id'] != user_id]
        self.save()

    def finalize_participants(self):
        """Finalize the participant list."""
        if not self.quick_recruitment_complete:
            self.quick_final_participants = self.quick_participants.copy()
            self.quick_recruitment_complete = True
            self.save()

    def reset_timer(self):
        """Reset the timer for the room."""
        self.quick_timer_started = False
        self.save()



class QuickChatMessage(models.Model):
    quick_room = models.ForeignKey(QuickChatRoom, on_delete=models.CASCADE)
    user_id = models.CharField(max_length=100)
    user_name = models.CharField(max_length=100)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user_name} ({self.timestamp.strftime("%Y-%m-%d %H:%M:%S")}): {self.message[:20]}'



# QuickQuickChatRoom for quick_match_chat_room_page.dart
class QuickQuickChatRoom(models.Model):
    quickquick_room_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    quickquick_room_name = models.CharField(max_length=100, default='default_room_name')
    quickquick_created_at = models.DateTimeField(auto_now_add=True)
    quickquick_updated_at = models.DateTimeField(auto_now=True)  # 최근 업데이트 시간 추가
    quickquick_participants = models.JSONField(default=list)
    quickquick_final_participants = models.JSONField(default=list, blank=True)  # 최종 참가자 추가
    quickquick_final_participants_saved = models.BooleanField(default=False)  # 최종 참가자 저장 여부
    quickquick_participant_count = models.IntegerField(default=0)  # 참가자 수 추가
    quickquick_departure = models.CharField(max_length=255, default='default_departure')
    quickquick_destination = models.CharField(max_length=255, default='default_destination')
    quickquick_departure_time = models.DateTimeField(null=True, blank=True)
    quickquick_recruitment_complete = models.BooleanField(default=False)
    quickquick_is_active = models.BooleanField(default=True)
    quickquick_is_settled = models.BooleanField(default=False)  # 정산 완료 여부 추가
    quickquick_chat_started = models.BooleanField(default=False)
    quickquick_max_participants = models.IntegerField(default=4)  # 최대 참가자 수 추가
    quickquick_min_participants = models.IntegerField(default=2)  # 최소 참가자 수 추가


    def __str__(self):
        return self.quickquick_room_name


class QuickQuickChatMessage(models.Model):
    quickquick_room = models.ForeignKey(QuickQuickChatRoom, on_delete=models.CASCADE)
    user_id = models.CharField(max_length=100)
    user_name = models.CharField(max_length=100)
    quickquick_message = models.TextField()
    quickquick_timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user_name}: {self.quickquick_message[:20]}'
