import json
from unittest.mock import patch
from django.test import TestCase, RequestFactory

from base.models import AISettings
from customer import views


class ChatAssistantViewTest(TestCase):
    def setUp(self):
        self.rf = RequestFactory()
        self.fake_restaurant = type("R", (), {"id": 1, "name": "R"})()

    def _post(self, body):
        req = self.rf.post(
            "/t/tok/chat/", data=json.dumps(body), content_type="application/json"
        )
        # session
        from django.contrib.sessions.backends.db import SessionStore
        req.session = SessionStore()
        return req

    @patch("customer.views.get_client_context")
    def test_disabled_returns_unavailable(self, mock_ctx):
        mock_ctx.return_value = (self.fake_restaurant, object(), object(), None)
        s = AISettings.load()
        s.is_enabled = False
        s.save()
        req = self._post({"message": "salut"})
        resp = views.chat_assistant(req, "tok")
        data = json.loads(resp.content)
        self.assertTrue(data.get("unavailable"))

    @patch("customer.views.ask")
    @patch("customer.views.get_client_context")
    def test_returns_reply_and_persists_history(self, mock_ctx, mock_ask):
        mock_ctx.return_value = (self.fake_restaurant, object(), object(), None)
        mock_ask.return_value = {"reply": "Bonjour", "actions": []}
        s = AISettings.load()
        s.is_enabled = True
        s.api_key = "k"
        s.save()
        req = self._post({"message": "salut"})
        resp = views.chat_assistant(req, "tok")
        data = json.loads(resp.content)
        self.assertEqual(data["reply"], "Bonjour")
        hist = req.session.get("chat_1_tok")
        self.assertEqual(len(hist), 2)  # user + assistant

    @patch("customer.views.ask")
    @patch("customer.views.get_client_context")
    def test_message_limit_blocks(self, mock_ctx, mock_ask):
        mock_ctx.return_value = (self.fake_restaurant, object(), object(), None)
        mock_ask.return_value = {"reply": "x", "actions": []}
        s = AISettings.load()
        s.is_enabled = True
        s.api_key = "k"
        s.max_messages_per_session = 1
        s.save()
        req = self._post({"message": "deuxieme"})
        req.session["chat_1_tok"] = [{"role": "user", "content": "premier"},
                                     {"role": "assistant", "content": "r"}]
        resp = views.chat_assistant(req, "tok")
        data = json.loads(resp.content)
        self.assertTrue(data.get("limit_reached"))
        mock_ask.assert_not_called()

    @patch("customer.views.get_client_context")
    def test_empty_message(self, mock_ctx):
        mock_ctx.return_value = (self.fake_restaurant, object(), object(), None)
        s = AISettings.load()
        s.is_enabled = True
        s.api_key = "k"
        s.save()
        req = self._post({"message": "   "})
        resp = views.chat_assistant(req, "tok")
        data = json.loads(resp.content)
        self.assertEqual(data["actions"], [])
