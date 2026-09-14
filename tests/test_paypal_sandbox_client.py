import os
import unittest
from unittest import mock

from app.paypal_sandbox_client import PayPalSandboxConfig, SANDBOX_API_BASE, sandbox_status


class PayPalSandboxConfigTests(unittest.TestCase):
    def test_not_configured_without_credentials(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(PayPalSandboxConfig.from_env())
            status = sandbox_status()
            self.assertEqual(status["runtime"], "PAYPAL_SIMULATOR")
            self.assertFalse(status["sandbox_credentials_configured"])
            self.assertFalse(status["webhook_id_configured"])
            self.assertFalse(status["production_authorized"])
            self.assertEqual(status["api_base"], SANDBOX_API_BASE)

    def test_configured_with_credentials(self):
        env = {
            "PAYPAL_SANDBOX_CLIENT_ID": "sandbox-client",
            "PAYPAL_SANDBOX_CLIENT_SECRET": "sandbox-secret",
            "PAYPAL_SANDBOX_WEBHOOK_ID": "sandbox-webhook",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = PayPalSandboxConfig.from_env()
            self.assertIsNotNone(cfg)
            self.assertEqual(cfg.client_id, "sandbox-client")
            self.assertEqual(cfg.client_secret, "sandbox-secret")
            self.assertEqual(cfg.webhook_id, "sandbox-webhook")
            self.assertEqual(cfg.api_base, SANDBOX_API_BASE)
            status = sandbox_status()
            self.assertEqual(status["runtime"], "PAYPAL_SANDBOX")
            self.assertTrue(status["sandbox_credentials_configured"])
            self.assertTrue(status["webhook_id_configured"])
            self.assertFalse(status["production_authorized"])


if __name__ == "__main__":
    unittest.main()
