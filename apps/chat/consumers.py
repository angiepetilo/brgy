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
        if not validate_websocket_origin(self.scope):
            await self.close(code=4003)
            return

        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
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

        # Same per-user send limit as the HTTP chat views (RATE_LIMITS['chat_send']).
        retry_after = await self.check_send_rate()
        if retry_after:
            await self.send(text_data=json.dumps({
                "type": "error",
                "error": "rate_limited",
                "retry_after": retry_after,
                "message": "You are sending messages too quickly. Please wait a moment.",
            }))
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
    def check_send_rate(self):
        from apps.core.ratelimit import hit, resolve_rate
        limit, period = resolve_rate('chat_send')
        return hit('chat_send:user', f'u{self.user.pk}', limit, period)

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


from urllib.parse import urlparse
from django.conf import settings


def validate_websocket_origin(scope):
    """
    Validates the WebSocket Origin header against ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS.
    """
    headers = dict(scope.get("headers", []))
    origin = headers.get(b"origin")
    if not origin:
        return getattr(settings, 'DEBUG', False) or getattr(settings, 'ALLOW_EMPTY_WS_ORIGIN', True)
    try:
        origin_str = origin.decode("utf-8")
        parsed = urlparse(origin_str)
        host = (parsed.netloc or parsed.path).split(":")[0].lower()
        if host in ['localhost', '127.0.0.1', 'testserver']:
            return True
        allowed_hosts = [h.strip().lower() for h in getattr(settings, 'ALLOWED_HOSTS', []) if h.strip() != '*']
        if host in allowed_hosts:
            return True
        trusted = [urlparse(t).netloc.split(":")[0].lower() for t in getattr(settings, 'CSRF_TRUSTED_ORIGINS', [])]
        return host in trusted
    except Exception:
        return False


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Personal notification consumer.
    - Requires authenticated user
    - Validates Origin header
    - Joins ONLY that user's own group (user_<id>)
    """

    async def connect(self):
        # 1. Validate Origin
        if not validate_websocket_origin(self.scope):
            await self.close(code=4003)
            return

        # 2. Require authenticated user
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        # 3. Join ONLY that user's own group
        self.user_group = f"user_{self.user.id}"
        await self.channel_layer.group_add(
            self.user_group,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "user_group"):
            await self.channel_layer.group_discard(
                self.user_group,
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
