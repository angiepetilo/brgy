import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from apps.chat.models import Message, Notification

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    """
    Direct 1-on-1 WebSocket chat consumer between Residents and Barangay Admins.
    """

    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        # other_user_id from url route
        self.other_user_id = int(self.scope["url_route"]["kwargs"]["user_id"])
        
        # Consistent deterministic room group name
        user_ids = sorted([self.user.id, self.other_user_id])
        self.room_group_name = f"chat_{user_ids[0]}_{user_ids[1]}"

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        content = data.get("message", "").strip()
        if not content:
            return

        # Save message in database
        saved_msg = await self.save_message(self.user.id, self.other_user_id, content)

        # Broadcast to room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message_id": saved_msg["id"],
                "sender_id": self.user.id,
                "sender_name": self.user.get_full_name() or self.user.username,
                "sender_role": self.user.get_role_display(),
                "content": content,
                "created_at": saved_msg["created_at"],
            }
        )

        # Send real-time notification to recipient's personal notification channel
        recipient_group = f"user_{self.other_user_id}"
        await self.channel_layer.group_send(
            recipient_group,
            {
                "type": "send_notification",
                "title": f"New message from {self.user.get_full_name() or self.user.username}",
                "message": content[:60] + ("..." if len(content) > 60 else ""),
                "notification_type": "chat",
                "link_url": f"/chat/{self.user.id}/",
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def save_message(self, sender_id, recipient_id, content):
        sender = User.objects.get(id=sender_id)
        recipient = User.objects.get(id=recipient_id)
        msg = Message.objects.create(
            sender=sender,
            recipient=recipient,
            content=content
        )
        # Create unread notification for recipient
        Notification.objects.create(
            recipient=recipient,
            sender=sender,
            title=f"Message from {sender.get_full_name() or sender.username}",
            message=content[:100],
            notification_type=Notification.TYPE_CHAT,
            link_url=f"/chat/{sender.id}/"
        )
        return {
            "id": msg.id,
            "created_at": msg.created_at.strftime("%b %d, %Y %I:%M %p"),
        }


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Global notification & broadcast consumer for Kapitan status changes,
    appointment status updates, verification alerts, and badge counters.
    """

    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        self.user_group = f"user_{self.user.id}"
        self.broadcast_group = "barangay_broadcast"

        # Join personal user group
        await self.channel_layer.group_add(
            self.user_group,
            self.channel_name
        )

        # Join public barangay broadcast group
        await self.channel_layer.group_add(
            self.broadcast_group,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "user_group"):
            await self.channel_layer.group_discard(
                self.user_group,
                self.channel_name
            )
        if hasattr(self, "broadcast_group"):
            await self.channel_layer.group_discard(
                self.broadcast_group,
                self.channel_name
            )

    async def receive(self, text_data):
        pass

    async def send_notification(self, event):
        """Send personal notification to individual user"""
        await self.send(text_data=json.dumps({
            "type": "notification",
            "title": event.get("title", "Barangay Notification"),
            "message": event.get("message", ""),
            "notification_type": event.get("notification_type", "general"),
            "link_url": event.get("link_url", "#"),
        }))

    async def kapitan_status_update(self, event):
        """Broadcast live Kapitan status update to all connected users"""
        await self.send(text_data=json.dumps({
            "type": "kapitan_status",
            "status": event.get("status"),
            "status_display": event.get("status_display"),
            "leave_reason": event.get("leave_reason", ""),
            "return_date": event.get("return_date", ""),
            "updated_at": event.get("updated_at", ""),
        }))

    async def announcement_broadcast(self, event):
        """Broadcast new announcement banner to all connected users"""
        await self.send(text_data=json.dumps({
            "type": "announcement",
            "title": event.get("title"),
            "category": event.get("category"),
            "created_at": event.get("created_at"),
            "announcement_id": event.get("announcement_id"),
        }))
