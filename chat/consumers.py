from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
import aioredis
from signup.models import UserInfo
from .models import ChatRoom, ChatMessage
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Initialize Redis for WebSocket connections
redis = aioredis.from_url('redis://127.0.0.1:6379')

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        self.user_id = self.scope['query_string'].decode().split('=')[1]
        
        # Check if user is reconnecting
        reconnecting = await self.is_user_reconnecting()

        # Authenticate user before connecting
        if not await self.is_user_authenticated():
            await self.close()
            return

        # Check if the chat room exists
        try:
            self.chat_room = await sync_to_async(ChatRoom.objects.get)(room_id=self.room_id)
        except ChatRoom.DoesNotExist:
            await self.close(code=404)
            return

        # Add the user to the WebSocket group and accept the connection
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # Clear existing Redis entries for the user to prevent duplication
        await self.clear_existing_participant()

        # Set the first user to join the room as the leader if not reconnecting
        is_first_participant = len(self.chat_room.participants) == 0 and not reconnecting
        await self.add_user_to_participants(as_leader=is_first_participant)

        # Notify all participants if it's a new connection, not a reconnection
        if not reconnecting:
            user = await self.get_user_info(self.user_id)
            if user:
                await self.send_participants_update(
                    f"{user.name}님이 방에 참여하였습니다.",
                    is_system_message=True
                )
        
        # Mark the user as connected in Redis
        await redis.sadd(self.room_group_name, self.user_id)

    async def disconnect(self, close_code):
        # Only handle disconnect if the user was not just temporarily away
        if await self.is_user_in_room():
            user = await self.get_user_info(self.user_id)
            is_leader = any(p['leader'] for p in self.chat_room.participants if p['user_id'] == self.user_id)

            # Notify all participants that the user is leaving
            if user:
                await self.send_participants_update(
                    f"{user.name}님이 방을 나갔습니다.",
                    is_system_message=True
                )
            
            # Update Redis and participants in the database
            await self.update_participants(add=False)
            await self.remove_user_from_participants()

            # Only reassign leader if recruitment is not complete
            if not self.chat_room.recruitment_complete and is_leader:
                new_leader_name = await self.handle_leader_reassignment()
                if new_leader_name:
                    await self.send_participants_update(
                        f"{new_leader_name}님이 새로운 방장이 되었습니다.",
                        is_system_message=True
                    )

        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def is_user_reconnecting(self):
        """Check if the user was already connected recently to avoid duplicate join messages."""
        return await redis.sismember(self.room_group_name, self.user_id)

    async def clear_existing_participant(self):
        await redis.srem(self.room_group_name, self.user_id)

    async def update_participants(self, add):
        if add:
            await redis.sadd(self.room_group_name, self.user_id)
        else:
            await redis.srem(self.room_group_name, self.user_id)
        await self.send_participants_update(None, is_system_message=False)

    async def add_user_to_participants(self, as_leader=False):
        """Add the user as a participant. Assign as leader if specified."""
        user = await self.get_user_info(self.user_id)
        if user:
            # Ensure user is added only once
            self.chat_room.participants = [p for p in self.chat_room.participants if p['user_id'] != self.user_id]
            participant_data = {
                'user_id': self.user_id,
                'user_name': user.name,
                'leader': as_leader
            }
            self.chat_room.participants.append(participant_data)
            await sync_to_async(self.chat_room.save)()

    async def remove_user_from_participants(self):
        """Remove the user from the participants list."""
        self.chat_room.participants = [p for p in self.chat_room.participants if p['user_id'] != self.user_id]
        await sync_to_async(self.chat_room.save)()

    async def send_participants_update(self, message, is_system_message=False):
        """Send updated participant list to all clients."""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'participants_update',
                'message': message,
                'participants': await self.get_participants_with_leader(),
                'is_system_message': is_system_message
            }
        )

    async def is_user_authenticated(self):
        try:
            user = await sync_to_async(UserInfo.objects.get)(user_id=self.user_id)
            return True if user else False
        except UserInfo.DoesNotExist:
            logger.error(f"User with user_id {self.user_id} does not exist.")
            return False

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            user_id = data['user_id']
            command = data.get('command')
            message = data.get('message')
            timestamp = data.get('timestamp', self.get_current_timestamp())

            if command == "complete_recruitment":
                # Only the leader can complete recruitment
                if await self.is_user_leader(user_id):
                    self.chat_room.recruitment_complete = True
                    await sync_to_async(self.chat_room.save)()
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'recruitment_complete',
                            'message': "모집이 완료되었습니다. 이제 나가기 버튼을 사용할 수 없습니다.",
                            'block_exit': True
                        }
                    )
                else:
                    await self.send(text_data=json.dumps({
                        'message': 'Only the leader can complete recruitment.',
                        'status': 'error'
                    }))
            elif user_id and message:
                user = await self.get_user_info(user_id)
                await sync_to_async(ChatMessage.objects.create)(
                    room_id=self.room_id,
                    user_id=user_id,
                    user_name=user.name,
                    message=message,
                    timestamp=timestamp,
                )
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'user': user.name,
                        'message': message,
                        'timestamp': timestamp,
                        'user_id': user_id,
                    }
                )
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({'error': 'Invalid JSON'}))
        except KeyError:
            await self.send(text_data=json.dumps({'error': "Message missing 'user_id' or 'message'"}))

    async def chat_message(self, event):
        """Send chat message to WebSocket."""
        await self.send(text_data=json.dumps({
            'user': event['user'],
            'message': event['message'],
            'timestamp': event['timestamp'],
            'user_id': event['user_id'],
        }))

    async def participants_update(self, event):
        await self.send(text_data=json.dumps({
            'message': event.get('message', ''),
            'participants': event['participants'],
            'is_system_message': event.get('is_system_message', False),
        }))

    async def recruitment_complete(self, event):
        """Notify all participants that recruitment is complete and disable exit."""
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'status': 'Recruitment Complete',
            'block_exit': event.get('block_exit', True)  # Disable exit button on the client side
        }))

    async def settlement_complete(self, event):
        await self.send(text_data=json.dumps({
            'message': event.get('message'),
            'deeplink': event.get('deeplink'),
            'per_person_amount': event.get('per_person_amount'),
            'allow_exit': True
        }))

    async def is_user_in_room(self):
        participants = await self.get_participants()
        return self.user_id in participants

    async def get_participants(self):
        participants = await redis.smembers(self.room_group_name)
        return [p.decode('utf-8') for p in participants]

    async def get_participants_with_leader(self):
        self.chat_room = await sync_to_async(ChatRoom.objects.get)(room_id=self.room_id)
        return [
            {
                'user_id': participant['user_id'],
                'user_name': participant['user_name'],
                'leader': participant['leader'],
            }
            for participant in self.chat_room.participants
        ]

    async def get_user_info(self, user_id):
        try:
            return await sync_to_async(UserInfo.objects.get)(user_id=user_id)
        except UserInfo.DoesNotExist:
            logger.error(f"UserInfo with user_id {user_id} does not exist.")
            return None

    async def is_user_leader(self, user_id):
        """Check if the user is the leader."""
        return any(p['leader'] for p in self.chat_room.participants if p['user_id'] == user_id)

    async def handle_leader_reassignment(self):
        """Do not reassign the leader if recruitment is complete."""
        if self.chat_room.recruitment_complete:
            return None  # Do not reassign the leader if recruitment is complete

        self.chat_room = await sync_to_async(ChatRoom.objects.get)(room_id=self.room_id)
        is_leader = any(p['leader'] for p in self.chat_room.participants if p['user_id'] == self.user_id)
        new_leader_name = None
        if is_leader:
            remaining_participants = [p for p in self.chat_room.participants if p['user_id'] != self.user_id]
            if remaining_participants:
                remaining_participants[0]['leader'] = True
                new_leader_name = remaining_participants[0]['user_name']
            self.chat_room.participants = remaining_participants
            await sync_to_async(self.chat_room.save)()
        return new_leader_name

    def get_current_timestamp(self):
        return datetime.now(timezone.utc).isoformat()
