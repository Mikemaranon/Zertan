# web_server/user_m/user_manager.py

import datetime
import threading

import jwt
from werkzeug.security import check_password_hash, generate_password_hash

from data_m import DBManager


class UserManager:
    _instance = None
    _lock = threading.Lock()
    ROLE_ORDER = {
        "user": 0,
        "reviewer": 1,
        "examiner": 2,
        "administrator": 3,
    }

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(UserManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, secret_key="zertan-development-secret-key-2026-32b", db_manager=None):
        if hasattr(self, "initialized") and self.initialized:
            return

        self.db = db_manager or DBManager()
        self.secret_key = secret_key
        self.initialized = True

    def normalize_role(self, role):
        aliases = {"admin": "administrator"}
        return aliases.get((role or "user").strip().lower(), (role or "user").strip().lower())

    def user_has_role(self, user, required_role):
        if not user:
            return False
        user_role = self.normalize_role(user.get("role"))
        required = self.normalize_role(required_role)
        return self.ROLE_ORDER.get(user_role, -1) >= self.ROLE_ORDER.get(required, -1)

    def authenticate(self, username, password):
        user = self.db.users.get(username)
        if not user or user["status"] != "active":
            return None
        if check_password_hash(user["password_hash"], password):
            return user
        return None

    def get_token_from_cookie(self, request):
        return request.cookies.get("token")

    def get_request_token(self, request):
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header.split(" ", 1)[1]
        return None

    def check_user(self, request):
        token = self.get_token_from_cookie(request) or self.get_request_token(request)
        if not token:
            return None
        return self.get_user_from_token(token)

    def create_user(self, username, password, role="user", email=None, status="active"):
        if self.db.users.get(username):
            return None
        if email and self.db.users.get_by_email(email):
            return None
        normalized_role = self.normalize_role(role)
        password_hash = generate_password_hash(password)
        self.db.users.create(username, password_hash, role=normalized_role, email=email, status=status)
        return self.db.users.get(username)

    def update_user(self, user_id, username, email, role, status, password=None):
        normalized_role = self.normalize_role(role)
        self.db.users.update(user_id, username, email, normalized_role, status)
        if password:
            self.db.users.update_password(user_id, generate_password_hash(password))
        return self.db.users.get_by_id(user_id)

    def login(self, username, password):
        user = self.authenticate(username, password)
        if not user:
            return None

        token, expiration_time = self.generate_token(user)
        self.db.sessions.create(user["id"], token, expiration_time.isoformat())
        self.db.users.touch_last_login(user["id"])
        refreshed_user = self.db.users.get_by_id(user["id"])
        return {
            "token": token,
            "expires_at": expiration_time.isoformat(),
            "user": self.public_user(refreshed_user),
        }

    def logout(self, token):
        if token:
            self.db.sessions.delete(token)
        return True

    def get_user_from_token(self, token):
        if not self.validate_token(token):
            return None
        payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
        user_id = payload.get("user_id")
        user = self.db.users.get_by_id(user_id)
        if not user or user["status"] != "active":
            self.db.sessions.delete(token)
            return None
        return self.public_user(user)

    def generate_token(self, user):
        expiration_time = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
        payload = {
            "user_id": user["id"],
            "username": user["username"],
            "role": self.normalize_role(user["role"]),
            "exp": expiration_time,
        }
        token = jwt.encode(payload, self.secret_key, algorithm="HS256")
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        return token, expiration_time

    def validate_token(self, token):
        session = self.db.sessions.get(token)
        if not session:
            return False

        try:
            jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return True
        except jwt.ExpiredSignatureError:
            self.db.sessions.delete(token)
            return False
        except jwt.InvalidTokenError:
            self.db.sessions.delete(token)
            return False

    def public_user(self, user):
        if not user:
            return None
        return {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "role": self.normalize_role(user["role"]),
            "status": user["status"],
            "created_at": user["created_at"],
            "updated_at": user["updated_at"],
            "last_login_at": user["last_login_at"],
        }
