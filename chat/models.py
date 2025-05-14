from django.db import models
import uuid
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class ChatRoom(models.Model):
    room_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    room_name = models.CharField(max_length=100, default='default_room_name')
    created_at = models.DateTimeField(auto_now_add=True)
    participants = models.JSONField(default=list)
    final_participants = models.JSONField(default=list, blank=True)
    departure = models.CharField(max_length=255, default='default_departure')
    destination = models.CharField(max_length=255, default='default_destination')
    departure_time = models.DateTimeField(null=True, blank=True)
    chat_content = models.TextField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    settled_by = models.CharField(max_length=50, null=True, blank=True)
    recruitment_complete = models.BooleanField(default=False)
    settlement_complete = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    last_active = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Ensure departure_time is stored as UTC without timezone info
        if isinstance(self.departure_time, datetime) and self.departure_time.tzinfo is not None:
            self.departure_time = self.departure_time.astimezone(timezone.utc).replace(tzinfo=None)
        super().save(*args, **kwargs)

    def complete_recruitment(self):
        """Set recruitment as complete and save final participants."""
        self.recruitment_complete = True
        self.final_participants = self.participants.copy()
        self.save()
        logger.info(f"Recruitment completed for room {self.room_id}: {self.final_participants}")

    def __str__(self):
        return f"{self.room_name} (ID: {self.room_id})"

class ChatMessage(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="messages")
    user_id = models.CharField(max_length=100)
    user_name = models.CharField(max_length=100)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user_name} ({self.timestamp.strftime("%Y-%m-%d %H:%M:%S")}): {self.message[:20]}'
