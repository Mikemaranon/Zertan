__all__ = [
    "discover_domain_api_classes",
    "register_domain_apis",
    "QuestionPayloadParser",
]


def __getattr__(name):
    if name in {"discover_domain_api_classes", "register_domain_apis"}:
        from .domain_registry import discover_domain_api_classes, register_domain_apis

        return {
            "discover_domain_api_classes": discover_domain_api_classes,
            "register_domain_apis": register_domain_apis,
        }[name]
    if name == "QuestionPayloadParser":
        from .question_payload_parser import QuestionPayloadParser

        return QuestionPayloadParser
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
