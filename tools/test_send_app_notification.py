import contextlib
import io
import json
import os
import unittest
from unittest.mock import Mock, patch

import send_app_notification as sender


class NotificationSenderTests(unittest.TestCase):
    def test_preview_never_loads_credentials_or_sends(self):
        with patch.object(sender, "load_credentials") as creds, patch.object(sender, "deliver") as deliver:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(sender.main(["--title", "News", "--body", "New feature"]), 0)
            creds.assert_not_called()
            deliver.assert_not_called()

    def test_debug_and_production_have_separate_topics(self):
        self.assertEqual(sender.build_payload("A", "B")["message"]["topic"], "myrecon_announcements")
        self.assertEqual(sender.build_payload("A", "B", debug=True)["message"]["topic"], "myrecon_announcements_debug")

    def test_device_target_does_not_also_broadcast(self):
        message = sender.build_payload("A", "B", token="test-token")["message"]
        self.assertEqual(message["token"], "test-token")
        self.assertNotIn("topic", message)

    def test_reject_empty_and_oversized_messages(self):
        for title, body in [(" ", "B"), ("A", ""), ("A" * 121, "B"), ("A", "B" * 1801), ("A", "😀" * 1000)]:
            with self.subTest(title=title[:5], length=len(body)), self.assertRaises(ValueError):
                sender.build_payload(title, body)

    def test_validate_uses_validate_only(self):
        with patch.object(sender, "load_credentials", return_value={}), patch.object(sender, "deliver", return_value={}) as deliver:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(sender.main(["--title", "A", "--body", "B", "--validate"]), 0)
            self.assertTrue(deliver.call_args.args[0]["validate_only"])

    def test_send_requires_explicit_flag(self):
        with patch.object(sender, "load_credentials", return_value={}), patch.object(sender, "deliver", return_value={"name": "projects/test/messages/123"}) as deliver:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(sender.main(["--title", "A", "--body", "B", "--send"]), 0)
            self.assertFalse(deliver.call_args.args[0]["validate_only"])

    def test_wrong_project_credentials_rejected(self):
        with patch.dict(os.environ, {"FIREBASE_SERVICE_ACCOUNT": json.dumps({"project_id": "another-project"})}):
            with self.assertRaisesRegex(ValueError, "myrecon-bugsnaps"):
                sender.load_credentials()

    def test_http_request_uses_messaging_scope_and_authorized_payload(self):
        import jwt
        import requests
        auth = Mock()
        auth.json.return_value = {"access_token": "fake-access-token"}
        response = Mock(ok=True)
        response.json.return_value = {"name": "projects/test/messages/123"}
        payload = sender.build_payload("A", "B", validate=True)
        with patch.object(jwt, "encode", return_value="fake-assertion") as encode, patch.object(requests, "post", side_effect=[auth, response]) as post:
            sender.deliver(payload, {"client_email": "test@example.invalid", "private_key": "fake-key"})
        self.assertEqual(encode.call_args.args[0]["scope"], "https://www.googleapis.com/auth/firebase.messaging")
        self.assertEqual(post.call_args.kwargs["json"], payload)
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer fake-access-token")


if __name__ == "__main__":
    unittest.main()
