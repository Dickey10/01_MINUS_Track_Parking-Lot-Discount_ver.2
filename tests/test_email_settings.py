import asyncio
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.config import settings
from app.main import save_email_settings
from app.models import EmailSettingsUpdate


class EmailSettingsTests(unittest.TestCase):
    def test_changing_sender_requires_new_password(self):
        req = EmailSettingsUpdate(
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            smtp_user="new-sender@example.com",
            smtp_password="",
            alert_email="alerts@example.com",
        )

        original_user = settings.smtp_user
        original_password = settings.smtp_password
        settings.smtp_user = "old-sender@example.com"
        settings.smtp_password = "existing-app-password"

        try:
            with patch("app.main.update_env_values") as update_env_values, patch("app.main.audit"):
                with self.assertRaises(HTTPException) as ctx:
                    asyncio.run(save_email_settings(req, {"id": 1, "role": "admin"}))

            self.assertEqual(ctx.exception.status_code, 400)
            self.assertIn("app password", ctx.exception.detail)
            update_env_values.assert_not_called()
        finally:
            settings.smtp_user = original_user
            settings.smtp_password = original_password


if __name__ == "__main__":
    unittest.main()
