import json
import tempfile
import unittest
from pathlib import Path

from src.backend.n0jcg_licensing.client import (
    LICENSE_API_URL,
    LicenseClient,
    LicenseError,
    installation_serial_from_identity,
)


class CapturingResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self.payload


class CapturingOpener:
    def __init__(self):
        self.request = None

    def __call__(self, request, timeout):
        self.request = request
        return CapturingResponse({"valid": False, "error": "test rejection"})


class AirTrafficLicensingTests(unittest.TestCase):
    def test_worker_payload_url_and_user_agent_are_canonical(self):
        opener = CapturingOpener()
        expected_license = "N0JCG-AIR-ABCD-EFGH-JKLM-NPQR"
        expected_email = "operator@example.com"
        expected_installation = installation_serial_from_identity("air-traffic-test-installation")
        with tempfile.TemporaryDirectory() as directory:
            client = LicenseClient(
                product_slug="air-traffic",
                app_version="1.0.0",
                state_root=Path(directory),
                environment={
                    "N0JCG_LICENSE_API_URL": "https://stale.example.invalid",
                    "N0JCG_INSTALLATION_ID": "air-traffic-test-installation",
                },
                opener=opener,
                now=lambda: 1700000000,
            )
            with self.assertRaises(LicenseError):
                client.activate("  n0jcg-air-abcd-efgh-jklm-npqr  ", " Operator@Example.COM ")

        self.assertIsNotNone(opener.request)
        submitted = json.loads(opener.request.data.decode("utf-8"))
        self.assertEqual(submitted["license_serial"], expected_license)
        self.assertEqual(submitted["email"], expected_email)
        self.assertEqual(submitted["installation_serial"], expected_installation)
        self.assertEqual(submitted["product_slug"], "air-traffic")
        self.assertEqual(submitted["app_version"], "1.0.0")
        self.assertEqual(opener.request.get_header("User-agent"), "N0JCG-Air-Traffic/1.0.0")
        self.assertEqual(client.api_url, LICENSE_API_URL)

    def test_invalid_credentials_are_rejected_before_network_request(self):
        opener = CapturingOpener()
        with tempfile.TemporaryDirectory() as directory:
            client = LicenseClient(
                product_slug="air-traffic",
                app_version="1.0.0",
                state_root=Path(directory),
                opener=opener,
            )
            with self.assertRaises(LicenseError):
                client.activate("not-a-license", "not-an-email")
        self.assertIsNone(opener.request)


if __name__ == "__main__":
    unittest.main()
