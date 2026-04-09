import pathlib
import unittest


class TestNoPlaintextSecrets(unittest.TestCase):
    def test_no_plaintext_api_keys_in_python_files(self):
        repo = pathlib.Path(__file__).resolve().parents[1]
        patterns = ["AIza", "sk-proj-", "sk-"]
        ignore = {"tests/test_no_plaintext_secrets.py"}

        hits = []
        for path in repo.rglob("*.py"):
            rel = path.relative_to(repo).as_posix()
            if rel in ignore:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for p in patterns:
                if p in text:
                    hits.append((rel, p))

        self.assertEqual(hits, [], f"发现疑似明文密钥: {hits}")


if __name__ == "__main__":
    unittest.main()
