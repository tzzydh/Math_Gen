import tempfile
import unittest
from pathlib import Path

from core import db


class TestDB(unittest.TestCase):
    def test_org_user_crud(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "test.db")
            db.init_db(db_path)

            org_id = db.create_org(name="Demo Org", db_path=db_path)
            self.assertTrue(org_id > 0)

            orgs = db.list_orgs(db_path=db_path)
            self.assertEqual(len(orgs), 1)
            self.assertEqual(orgs[0]["name"], "Demo Org")

            user_id = db.create_user(
                org_id=org_id,
                role="teacher",
                name="Alice",
                email="a@example.com",
                password="pass123",
                db_path=db_path,
            )
            self.assertTrue(user_id > 0)

            users = db.list_users(org_id=org_id, db_path=db_path)
            self.assertEqual(len(users), 1)
            self.assertEqual(users[0]["name"], "Alice")

            auth_user = db.verify_user(org_id=org_id, name="Alice", password="pass123", db_path=db_path)
            self.assertIsNotNone(auth_user)

            qid = db.create_question(
                org_id=org_id,
                stem="1+1=?",
                options_json='["1","2","3","4"]',
                answer="2",
                analysis="basic",
                difficulty="易",
                chapter="第1讲 集合",
                created_by=user_id,
                db_path=db_path,
            )
            self.assertTrue(qid > 0)
            qs = db.list_questions(org_id=org_id, db_path=db_path)
            self.assertEqual(len(qs), 1)

    def test_create_user_invalid_org(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "test.db")
            db.init_db(db_path)
            with self.assertRaises(ValueError):
                db.create_user(org_id=999, role="teacher", name="Bob", db_path=db_path)


if __name__ == "__main__":
    unittest.main()
