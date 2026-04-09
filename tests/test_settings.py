import os
import unittest

from core.settings import require_env


class TestRequireEnv(unittest.TestCase):
    def test_require_env_returns_value(self):
        os.environ["UNIT_TEST_ENV_KEY"] = "ok"
        self.assertEqual(require_env("UNIT_TEST_ENV_KEY"), "ok")

    def test_require_env_raises_when_missing(self):
        if "UNIT_TEST_ENV_MISSING" in os.environ:
            del os.environ["UNIT_TEST_ENV_MISSING"]
        with self.assertRaises(RuntimeError):
            require_env("UNIT_TEST_ENV_MISSING")


if __name__ == "__main__":
    unittest.main()
