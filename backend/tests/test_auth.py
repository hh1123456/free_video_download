import unittest

from fastapi.testclient import TestClient

from app.main import app


class AuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_protected_api_requires_login(self) -> None:
        response = self.client.post("/api/parse", json={"url": "https://example.com/video"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "请先登录")

    def test_login_rejects_wrong_password(self) -> None:
        response = self.client.post(
            "/api/auth/login",
            json={"username": "player", "password": "wrong"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "账号或密码错误")

    def test_login_me_and_logout_flow(self) -> None:
        login = self.client.post(
            "/api/auth/login",
            json={"username": "player", "password": "295056"},
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json(), {"username": "player"})
        self.assertIn("session", login.cookies)

        me = self.client.get("/api/auth/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json(), {"username": "player"})

        logout = self.client.post("/api/auth/logout")
        self.assertEqual(logout.status_code, 200)

        after_logout = self.client.get("/api/auth/me")
        self.assertEqual(after_logout.status_code, 401)


if __name__ == "__main__":
    unittest.main()
