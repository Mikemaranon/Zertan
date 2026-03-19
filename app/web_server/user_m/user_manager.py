# web_server/user_m/user_manager.py

import datetime

import jwt
from werkzeug.security import check_password_hash, generate_password_hash

from data_m import DBManager
from runtime_config import get_runtime_config


class UserManager:
    ROLE_ORDER = {
        "user": 0,
        "reviewer": 1,
        "examiner": 2,
        "administrator": 3,
    }

    def __init__(self, secret_key=None, db_manager=None, runtime_config=None):
        config = dict(runtime_config or get_runtime_config())
        self.db = db_manager or DBManager()
        self.secret_key = secret_key or config["secret_key"]
        self.jwt_lifetime_hours = config["jwt_lifetime_hours"]

    def normalize_role(self, role):
        aliases = {"admin": "administrator"}
        return aliases.get((role or "user").strip().lower(), (role or "user").strip().lower())

    def normalize_login_name(self, login_name):
        return (login_name or "").strip().lower()

    def normalize_display_name(self, display_name, fallback=""):
        value = (display_name or "").strip()
        return value or (fallback or "").strip()

    def user_has_role(self, user, required_role):
        if not user:
            return False
        user_role = self.normalize_role(user.get("role"))
        required = self.normalize_role(required_role)
        return self.ROLE_ORDER.get(user_role, -1) >= self.ROLE_ORDER.get(required, -1)

    def authenticate(self, login_name, password):
        user = self.db.users.get_by_login_name(self.normalize_login_name(login_name))
        if not user or user["status"] != "active":
            return None
        if check_password_hash(user["password_hash"], password):
            return user
        return None

    def get_token_from_cookie(self, request):
        return request.cookies.get("token")

    def check_user(self, request):
        token = self.get_token_from_cookie(request)
        if not token:
            return None
        return self.get_user_from_token(token)

    def create_user(self, display_name, login_name, password, role="user", status="active", group_ids=None):
        normalized_login = self.normalize_login_name(login_name)
        normalized_display = self.normalize_display_name(display_name, fallback=normalized_login)
        if not normalized_login or not normalized_display:
            return None
        if self.db.users.get_by_login_name(normalized_login):
            return None
        normalized_role = self.normalize_role(role)
        password_hash = generate_password_hash(password)
        self.db.users.create(
            normalized_login,
            normalized_display,
            password_hash,
            role=normalized_role,
            status=status,
        )
        created_user = self.db.users.get_by_login_name(normalized_login)
        if created_user and group_ids is not None:
            self.db.groups.set_memberships_for_user(created_user["id"], group_ids)
            created_user = self.db.users.get_by_id(created_user["id"])
        return created_user

    def update_user(self, user_id, display_name, login_name, role, status, password=None, group_ids=None):
        normalized_login = self.normalize_login_name(login_name)
        normalized_display = self.normalize_display_name(display_name, fallback=normalized_login)
        existing = self.db.users.get_by_id(user_id)
        if not existing or not normalized_login or not normalized_display:
            return None
        conflict = self.db.users.get_by_login_name(normalized_login)
        if conflict and conflict["id"] != user_id:
            return None
        normalized_role = self.normalize_role(role)
        self.db.users.update(user_id, normalized_display, normalized_login, normalized_role, status)
        if password:
            self.db.users.update_password(user_id, generate_password_hash(password))
        if group_ids is not None:
            self.db.groups.set_memberships_for_user(user_id, group_ids)
        return self.db.users.get_by_id(user_id)

    def update_profile(self, user_id, display_name, current_password="", new_password="", confirm_password=""):
        user = self.db.users.get_by_id(user_id)
        if not user:
            raise ValueError("User not found.")

        normalized_display = self.normalize_display_name(display_name, fallback=user["display_name"])
        if not normalized_display:
            raise ValueError("Name is required.")

        password_fields = [current_password or "", new_password or "", confirm_password or ""]
        filled_count = sum(1 for value in password_fields if value.strip())
        if filled_count not in (0, 3):
            raise ValueError(
                "To change the password, complete current password, new password, and confirm new password, or leave all three blank."
            )
        if filled_count == 3:
            if not check_password_hash(user["password_hash"], current_password):
                raise ValueError("Current password is incorrect.")
            if new_password != confirm_password:
                raise ValueError("New password and confirmation do not match.")
            self.db.users.update_password(user_id, generate_password_hash(new_password))

        self.db.users.update_profile(user_id, normalized_display)
        return self.db.users.get_by_id(user_id)

    def update_avatar(self, user_id, avatar_path):
        self.db.users.update_avatar(user_id, avatar_path)
        return self.db.users.get_by_id(user_id)

    def login(self, login_name, password):
        user = self.authenticate(login_name, password)
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
        expiration_time = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=self.jwt_lifetime_hours)
        payload = {
            "user_id": user["id"],
            "login_name": user["login_name"],
            "display_name": user["display_name"],
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
            "username": user["display_name"],
            "login_name": user["login_name"],
            "display_name": user["display_name"],
            "role": self.normalize_role(user["role"]),
            "status": user["status"],
            "avatar_path": user.get("avatar_path"),
            "created_at": user["created_at"],
            "updated_at": user["updated_at"],
            "last_login_at": user["last_login_at"],
        }
