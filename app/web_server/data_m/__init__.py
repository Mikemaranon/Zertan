# data_m/__init__.py

__all__ = [
    "DBManager",
]


def __getattr__(name):
    if name == "DBManager":
        from .db_manager import DBManager

        return DBManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
