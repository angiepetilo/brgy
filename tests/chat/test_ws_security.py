import unittest
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from channels.testing import WebsocketCommunicator
from apps.chat.consumers import NotificationConsumer, ChatConsumer, validate_websocket_origin
from apps.chat.services import create_notification
from apps.chat.models import Notification

User = get_user_model()


class WebSocketSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='ws_user',
            email='ws_user@example.com',
            password='Password123!',
            status=User.STATUS_ACTIVE
        )

    def test_create_notification_channel_layer_down_does_not_crash(self):
        """Rule 1: create_notification must never fail if the channel layer is down (catch, log, continue)."""
        with patch('channels.layers.get_channel_layer') as mock_gl:
            mock_layer = mock_gl.return_value
            mock_layer.group_send.side_effect = ConnectionError("Redis / Channel layer is unreachable")

            notif = create_notification(
                recipient=self.user,
                title="Test Notice",
                message="Testing channel layer tolerance",
                action_type="message"
            )
            # Must successfully create database record despite channel failure
            self.assertIsNotNone(notif)
            self.assertTrue(Notification.objects.filter(id=notif.id).exists())

    async def test_websocket_requires_authenticated_user(self):
        """Rule 2: WebSocket consumers must require an authenticated user and reject anonymous connections."""
        # Test anonymous connection to NotificationConsumer
        communicator = WebsocketCommunicator(NotificationConsumer.as_asgi(), "/ws/notifications/")
        communicator.scope["user"] = AnonymousUser()
        connected, close_code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(close_code, 4001)

    async def test_websocket_validates_origin(self):
        """Rule 3a: WebSocket consumer must validate Origin and reject untrusted domains."""
        communicator = WebsocketCommunicator(NotificationConsumer.as_asgi(), "/ws/notifications/")
        communicator.scope["user"] = self.user
        communicator.scope["headers"] = [
            (b"origin", b"https://evil-attacker-phishing-domain.com")
        ]
        connected, close_code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(close_code, 4003)

    async def test_websocket_joins_only_own_group(self):
        """Rule 3b: WebSocket consumers must join only that user's own group."""
        consumer = NotificationConsumer()
        consumer.scope = {
            "user": self.user,
            "headers": [(b"origin", b"http://localhost")]
        }
        consumer.channel_name = "test_channel_123"
        joined_groups = []

        class MockChannelLayer:
            async def group_add(self, group, channel):
                joined_groups.append(group)
            async def group_discard(self, group, channel):
                pass

        consumer.channel_layer = MockChannelLayer()
        async def mock_close(code=None): pass
        async def mock_accept(): pass
        consumer.close = mock_close
        consumer.accept = mock_accept

        await consumer.connect()
        # Verify joined groups contains strictly user_<id> and no other broadcast/foreign groups
        self.assertEqual(joined_groups, [f"user_{self.user.id}"])
