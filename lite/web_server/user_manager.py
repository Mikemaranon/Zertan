import secrets

from app.web_server.user_m.user_manager import UserManager


class LiteUserManager(UserManager):
    def __init__(self, secret_key=None, db_manager=None, runtime_config=None):
        super().__init__(secret_key=secret_key, db_manager=db_manager, runtime_config=runtime_config)
        self.local_user_login = self.normalize_login_name(self.runtime_config.get("lite_user_login") or "lite")
        self.local_user_display_name = self.normalize_display_name(
            self.runtime_config.get("lite_user_display_name"),
            fallback="Local User",
        )
        self.local_user_role = self.normalize_role(self.runtime_config.get("lite_user_role") or "administrator")

    def check_user(self, request):
        return self.public_user(self.ensure_local_user())

    def ensure_local_user(self):
        existing_user = self.db.users.get_by_login_name(self.local_user_login)
        if existing_user:
            needs_update = any(
                (
                    existing_user["status"] != "active",
                    self.normalize_display_name(existing_user["display_name"]) != self.local_user_display_name,
                    self.normalize_role(existing_user["role"]) != self.local_user_role,
                )
            )
            if needs_update:
                self.db.users.update(
                    existing_user["id"],
                    self.local_user_display_name,
                    self.local_user_login,
                    self.local_user_role,
                    "active",
                )
                existing_user = self.db.users.get_by_id(existing_user["id"])
            return existing_user

        password = secrets.token_urlsafe(32)
        created_user = self.create_user(
            self.local_user_display_name,
            self.local_user_login,
            password,
            role=self.local_user_role,
            status="active",
        )
        if created_user:
            return created_user

        return self.db.users.get_by_login_name(self.local_user_login)
