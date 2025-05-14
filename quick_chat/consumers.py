import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from quick_chat.models import QuickChatRoom, QuickChatMessage
from asgiref.sync import sync_to_async
from django.apps import apps
import asyncio
import aioredis
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO)

REDIS_URL = 'redis://127.0.0.1:6379'

class QuickChatConsumer(AsyncWebsocketConsumer):
    countdown_task = None
    current_countdown = 30

    async def connect(self):
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.user_id = self.scope["query_string"].decode().split("user_id=")[1]
        self.room_group_name = f"quick_chat_{self.room_id}"

        self.redis = await aioredis.from_url(REDIS_URL)

        QuickChatRoom = apps.get_model("quick_chat", "QuickChatRoom")
        try:
            self.room = await sync_to_async(QuickChatRoom.objects.get)(quick_room_id=self.room_id)
        except QuickChatRoom.DoesNotExist:
            logger.info(f"[{self.room_id}] Room does not exist. Closing connection.")
            await self.close()
            return

        if self.room.quick_recruitment_complete:
            logger.info(f"[{self.room_id}] Recruitment is complete. User {self.user_id} cannot join.")
            await self.close()
            return

        await self.add_participant()
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        countdown = await self.redis.get(f"room_{self.room_id}_timer") or self.current_countdown
        self.current_countdown = int(countdown)
        logger.info(f"[{self.room_id}] User {self.user_id} connected. Timer initialized to {self.current_countdown} seconds.")
        await self.send(json.dumps({"type": "timer_update", "countdown": self.current_countdown}))

        await self.mark_ready()
        await self.broadcast_participants_update()
        await self.handle_participant_count()

    async def disconnect(self, close_code):
        if not hasattr(self, "room") or not self.room:
            return

        await self.remove_participant()
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        if self.redis:
            await self.redis.close()

    async def add_participant(self):
        if any(p["user_id"] == self.user_id for p in self.room.quick_participants):
            logger.info(f"[{self.room_id}] User {self.user_id} is already a participant.")
            return

        if len(self.room.quick_participants) >= 4:
            logger.info(f"[{self.room_id}] Room is full. User {self.user_id} cannot join.")
            await self.close()
            return

        user = await sync_to_async(apps.get_model("signup", "UserInfo").objects.get)(user_id=self.user_id)
        participant_data = {"user_id": self.user_id, "user_name": user.name, "ready": False}
        self.room.quick_participants.append(participant_data)
        await sync_to_async(self.room.save)()
        logger.info(f"[{self.room_id}] User {self.user_id} joined. Current participants: {self.room.quick_participants}")

    async def mark_ready(self):
        for participant in self.room.quick_participants:
            if participant["user_id"] == self.user_id:
                participant["ready"] = True
        await sync_to_async(self.room.save)()

    async def remove_participant(self):
        self.room.quick_participants = [
            p for p in self.room.quick_participants if p["user_id"] != self.user_id
        ]
        await sync_to_async(self.room.save)()
        await self.broadcast_participants_update()

        participant_count = len(self.room.quick_participants)

        if participant_count == 0:
            try:
                await sync_to_async(self.room.delete)()
                logger.info(f"[{self.room_id}] Room deleted as it became empty.")
            except Exception:
                logger.error(f"[{self.room_id}] Error deleting room.")
            self.room = None
        elif participant_count == 1:
            await self.cancel_existing_timer()
            self.current_countdown = 30
            await self.redis.delete(f"room_{self.room_id}_timer")
            await self.broadcast_timer_reset()

    async def handle_participant_count(self):
        participant_count = len(self.room.quick_participants)
        await self.cancel_existing_timer()

        if participant_count == 2:
            self.current_countdown = 30
            self.countdown_task = asyncio.create_task(self.start_timer())
            logger.info(f"[{self.room_id}] 2 participants. Timer started at 30 seconds.")
        elif participant_count == 3:
            logger.info(f"[{self.room_id}] 3 participants. Assigning timer to user {self.user_id}.")
            self.countdown_task = asyncio.create_task(self.start_timer_for_user(self.user_id, self.current_countdown))
        elif participant_count == 4:
            logger.info(f"[{self.room_id}] 4 participants. Immediate recruitment.")
            await self.complete_recruitment()
        elif participant_count < 2:
            self.current_countdown = 30
            await self.broadcast_timer_reset()
            logger.info(f"[{self.room_id}] Less than 2 participants. Timer reset.")

    async def cancel_existing_timer(self):
        if self.countdown_task:
            logger.info(f"[{self.room_id}] Cancelling existing timer.")
            self.countdown_task.cancel()
            try:
                await self.countdown_task
            except asyncio.CancelledError:
                logger.info(f"[{self.room_id}] Timer cancelled successfully.")
            finally:
                self.countdown_task = None

    async def start_timer_for_user(self, user_id, countdown_time):
        logger.info(f"[{self.room_id}] Timer for user {user_id} initiated at {countdown_time} seconds.")
        while countdown_time > 0:
            await asyncio.sleep(1)
            countdown_time -= 1
            await self.send(json.dumps({
                "type": "start_countdown",
                "countdown": countdown_time,
            }))

        if countdown_time == 0:
            await self.complete_recruitment()

    async def start_timer(self):
        logger.info(f"[{self.room_id}] Timer started. Countdown from {self.current_countdown} seconds.")
        while self.current_countdown > 0:
            await asyncio.sleep(1)
            self.current_countdown -= 1
            await self.redis.set(f"room_{self.room_id}_timer", self.current_countdown)
            await self.broadcast_timer_update()

        if self.current_countdown == 0:
            await self.complete_recruitment()

    async def complete_recruitment(self):
        await asyncio.sleep(2)  # 안정성 추가
        self.room.quick_recruitment_complete = True

        # 참가자 목록 저장 후 확인 로그
        self.room.quick_final_participants = self.room.quick_participants.copy()
        await sync_to_async(self.room.save)()
        logger.info(f"[{self.room_id}] Final participants saved: {self.room.quick_final_participants}")

        await self.transfer_to_quickquick_chat()
        await self.channel_layer.group_send(self.room_group_name, {
            "type": "chat_start",
            "message": "Recruitment completed.",
            "participants": self.room.quick_final_participants,
        })
        await self.cancel_existing_timer()

    async def transfer_to_quickquick_chat(self):
        QuickQuickChatRoom = apps.get_model("quick_chat", "QuickQuickChatRoom")
        quickquick_room = QuickQuickChatRoom(
        quickquick_room_id=self.room.quick_room_id,
        quickquick_participants=self.room.quick_final_participants,
        quickquick_room_name=self.room.quick_room_name,  # Include room name
        quickquick_departure=self.room.quick_departure,  # Include departure
        quickquick_destination=self.room.quick_destination,
        )
        await sync_to_async(quickquick_room.save)()
        logger.info(f"[{self.room_id}] Room transferred to QuickQuickChatRoom.")

    async def broadcast_participants_update(self):
        await self.channel_layer.group_send(self.room_group_name, {
            "type": "participants_update",
            "participants": self.room.quick_participants,
        })

    async def broadcast_timer_update(self):
        await self.channel_layer.group_send(self.room_group_name, {
            "type": "timer_update",
            "countdown": self.current_countdown,
        })

    async def broadcast_timer_reset(self):
        await self.channel_layer.group_send(self.room_group_name, {
            "type": "timer_reset",
            "message": "Timer reset to 30 seconds.",
            "countdown": 30,
        })

    async def timer_update(self, event):
        await self.send(json.dumps({
            "type": "timer_update",
            "countdown": event.get("countdown", 30),
        }))

    async def timer_reset(self, event):
        await self.send(json.dumps({
            "type": "timer_reset",
            "message": event.get("message", "Timer reset."),
            "countdown": event.get("countdown", 30),
        }))

    async def participants_update(self, event):
        await self.send(json.dumps({
            "type": "participants_update",
            "participants": event["participants"],
        }))

    async def chat_start(self, event):
        await self.send(json.dumps({
            "type": "chat_start",
            "message": event["message"],
            "participants": event["participants"],
        }))












class QuickQuickChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'quickquick_chat_{self.room_id}'
        self.user_id = self.scope['query_string'].decode().split('user_id=')[1]

        # Initialize Redis connection
        self.redis = await aioredis.from_url(REDIS_URL)

        # Fetch the QuickQuickChatRoom instance
        try:
            self.chat_room = await sync_to_async(apps.get_model('quick_chat', 'QuickQuickChatRoom').objects.get)(
                quickquick_room_id=self.room_id
            )
        except apps.get_model('quick_chat', 'QuickQuickChatRoom').DoesNotExist:
            logger.error(f"Room with quickquick_room_id {self.room_id} does not exist.")
            await self.close()
            return

        # Retrieve user information
        user_info = await self.get_user_info(self.user_id)
        self.user_name = user_info.get('user_name', 'Unknown')

        # Add user to participants list in Redis
        await self.add_participant_to_redis()

        # Join the WebSocket group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # Broadcast updated participants list
        await self.broadcast_participants_update()
        logger.info(f"[{self.room_id}] User {self.user_name} connected to QuickQuickChat.")

    async def disconnect(self, close_code):
        # Remove user from participants list in Redis
        await self.remove_participant_from_redis()

        # Leave the WebSocket group and close Redis connection
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        await self.redis.close()

        # Broadcast updated participants list
        await self.broadcast_participants_update()
        logger.info(f"[{self.room_id}] User {self.user_name} disconnected.")

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')

        if message_type == 'initiate_settlement':
            await self.mark_settlement_complete()
        elif message_type == 'exit_to_review':
            await self.exit_to_review()
        else:
            message = data.get('message')
            link = data.get('link', None)

            # Save message to Redis and database, and broadcast to all participants
            if not await self.is_duplicate_message(message):
                await self.save_message_to_storage(message, link)
                # Broadcast message only once
                await self.broadcast_chat_message(message, link)

    async def broadcast_chat_message(self, message, link=None):
        """Broadcast chat message to all participants."""
        await self.channel_layer.group_send(self.room_group_name, {
            'type': 'chat_message',
            'message': message,
            'user_name': self.user_name,
            'user_id': self.user_id,
            'link': link
        })

    async def mark_settlement_complete(self):
        # Mark settlement complete in the QuickQuickChatRoom model
        self.chat_room.quickquick_is_settled = True
        await sync_to_async(self.chat_room.save)()

        # Generate the settlement link
        user_info = await self.get_user_info(self.user_id)
        base_link = user_info.get('kakaopay_deeplink', '')
        deeplink = f"{base_link}HEX_AMOUNT"  # Replace with actual hex amount logic

        # Notify all participants about settlement completion
        await self.channel_layer.group_send(self.room_group_name, {
            'type': 'settlement_complete',
            'message': '정산을 완료하였습니다. 위의 링크로 결제를 진행하고 나가기를 진행해주세요.',
            'deeplink': deeplink
        })
        logger.info(f"[{self.room_id}] Settlement marked as complete in QuickQuickChat.")

    async def exit_to_review(self):
        # Notify all participants that the user has left for the review page
        await self.channel_layer.group_send(self.room_group_name, {
            'type': 'exit_to_review',
            'message': f"{self.user_name} has exited to the review page."
        })
        logger.info(f"[{self.room_id}] User {self.user_name} exited to the review page.")

    async def chat_message(self, event):
        # Broadcast chat message to all participants
        message = event['message']
        user_name = event['user_name']
        user_id = event['user_id']
        link = event.get('link')

        message_data = {
            'type': 'chat_message',
            'user_name': user_name,
            'message': message,
            'user_id': user_id
        }

        if link:
            message_data['link'] = link

        await self.send(text_data=json.dumps(message_data))

    async def settlement_complete(self, event):
        # Broadcast settlement completion to all participants
        message = event['message']
        deeplink = event['deeplink']

        await self.send(text_data=json.dumps({
            'type': 'settlement_complete',
            'message': message,
            'deeplink': deeplink
        }))

    async def exit_to_review(self, event):
        # Notify user about exiting to the review page
        message = event['message']
        await self.send(text_data=json.dumps({
            'type': 'exit_to_review',
            'message': message
        }))

    async def participants_update(self, event):
        # Handler for participants update events
        participants = event['participants']
        await self.send(text_data=json.dumps({
            'type': 'participants_update',
            'participants': participants
        }))

    async def broadcast_participants_update(self):
        """Broadcast updated participant list from Redis."""
        participants = await self.redis.hgetall(f'participants_{self.room_id}')
        participants_list = [json.loads(value) for value in participants.values()]

        logger.info(f"[{self.room_id}] Broadcasting participants: {participants_list}")
        await self.channel_layer.group_send(self.room_group_name, {
            'type': 'participants_update',
            'participants': participants_list
        })

    async def add_participant_to_redis(self):
        """Add participant to Redis using unique keys."""
        await self.redis.hset(
            f'participants_{self.room_id}', self.user_id,
            json.dumps({'user_id': self.user_id, 'user_name': self.user_name})
        )

    async def remove_participant_from_redis(self):
        """Remove participant from Redis."""
        await self.redis.hdel(f'participants_{self.room_id}', self.user_id)

    async def save_message_to_storage(self, message, link=None):
        """Save message to Redis and the database."""
        message_data = {
            'user_id': self.user_id,
            'user_name': self.user_name,
            'quickquick_message': message,
            'quickquick_timestamp': datetime.now(timezone.utc).isoformat(),
        }
        if link:
            message_data['link'] = link

        # Save to Redis
        await self.redis.rpush(f'quickquick_chat_{self.room_id}', json.dumps(message_data))

        # Save to database
        await sync_to_async(apps.get_model('quick_chat', 'QuickQuickChatMessage').objects.create)(
            quickquick_room=self.chat_room,
            user_id=self.user_id,
            user_name=self.user_name,
            quickquick_message=message,
        )

    async def is_duplicate_message(self, message):
        """Check if the message is a duplicate."""
        messages = await self.redis.lrange(f'quickquick_chat_{self.room_id}', 0, -1)
        for msg in messages:
            msg_data = json.loads(msg)
            if msg_data['quickquick_message'] == message and msg_data['user_id'] == self.user_id:
                return True
        return False

    @sync_to_async
    def get_user_info(self, user_id):
        """Retrieve user information from UserInfo model."""
        User = apps.get_model('signup', 'UserInfo')
        user = User.objects.filter(user_id=user_id).first()
        if user:
            return {'user_name': user.name, 'kakaopay_deeplink': user.kakaopay_deeplink}
        return {'user_name': 'Unknown', 'kakaopay_deeplink': ''}
