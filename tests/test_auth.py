import unittest

from core.auth import create_token, verify_token


class TestAuth(unittest.TestCase):
    def test_token_roundtrip(self):
        token = create_token({"uid": 1, "org_id": 2, "role": "teacher", "name": "Alice"})
        payload = verify_token(token)
        self.assertEqual(payload["uid"], 1)
        self.assertEqual(payload["org_id"], 2)

    def test_token_invalid(self):
        with self.assertRaises(ValueError):
            verify_token("invalid.token")


if __name__ == "__main__":
    unittest.main()
