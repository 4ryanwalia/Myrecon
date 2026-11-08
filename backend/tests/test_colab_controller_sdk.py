"""Run with .venv/colab Python and unittest; no live Google requests.

Validates compatibility with the pinned SDK, independently of Flask fixtures.
"""
from pathlib import Path
from importlib.util import find_spec
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import colab_controller as controller


@unittest.skipUnless(find_spec("colab_cli"), "Run in the isolated Colab controller environment")
class ControllerSDKTests(unittest.TestCase):
    def setUp(self):
        from colab_cli.client import Assignment, PostAssignmentResponse
        proxy = {"token": "proxy-test", "url": "https://colab.research.google.com/tun/m/owned/",
                 "tokenExpiresInSeconds": 3600}
        self.created = PostAssignmentResponse.model_validate({"endpoint": "owned",
            "runtimeProxyInfo": proxy, "accelerator": "NONE", "variant": 0})
        self.existing = Assignment.model_validate({"endpoint": "owned", "runtimeProxyInfo": proxy})
        self.env = patch.dict(controller.os.environ, {
            "COLAB_GOOGLE_CREDENTIALS_JSON": '{"type":"authorized_user","client_id":"id",'
                '"client_secret":"secret","refresh_token":"refresh"}',
            "SCAN_WORKER_TOKEN": "dedicated-test-worker-token-" * 2})
        self.env.start()
        self.addCleanup(self.env.stop)

    def invoke(self, balance=1, assignments=None, fail=False):
        with patch("colab_cli.client.Client", autospec=True) as client_type, \
             patch("colab_cli.runtime.ColabRuntime", autospec=True) as runtime_type, \
             patch("google.auth.transport.requests.AuthorizedSession", autospec=True):
            client = client_type.return_value
            client.get_consumption_user_info.return_value = SimpleNamespace(paid_compute_units_balance=balance)
            client.assign.side_effect = assignments or [self.created]
            runtime = runtime_type.return_value
            runtime.execute_code.return_value = []
            if fail:
                runtime.execute_code.side_effect = RuntimeError("provider error containing secret")
            result = controller.run()
            return result, client, runtime

    def test_zero_balance_never_allocates(self):
        result, client, _ = self.invoke(balance=0)
        self.assertEqual(result, 75)
        client.assign.assert_not_called()

    def test_new_cpu_assignment_starts_once_and_is_cleaned_up(self):
        from colab_cli.client import Accelerator, Variant
        result, client, runtime = self.invoke()
        self.assertEqual(result, 0)
        self.assertEqual(client.assign.call_count, 1)
        self.assertEqual(client.assign.call_args.kwargs,
                         {"variant": Variant.DEFAULT, "accelerator": Accelerator.NONE})
        client.unassign.assert_called_once_with("owned")
        self.assertEqual(runtime.execute_code.call_args.kwargs["timeout"], 0)
        self.assertTrue(callable(runtime.execute_code.call_args.kwargs["output_hook"]))
        self.assertNotIn("refresh", runtime.execute_code.call_args.args[0])

    def test_reused_assignment_reaps_only_its_own_runtime(self):
        result, client, _ = self.invoke(assignments=[self.existing, self.created])
        self.assertEqual(result, 0)
        self.assertEqual(client.assign.call_count, 2)
        self.assertEqual([call.args for call in client.unassign.call_args_list], [("owned",), ("owned",)])
        client.list_assignments.assert_not_called()

    def test_failed_remote_execution_releases_assignment(self):
        result, client, _ = self.invoke(fail=True)
        self.assertEqual(result, 1)
        client.unassign.assert_called_once_with("owned")


if __name__ == "__main__":
    unittest.main()
