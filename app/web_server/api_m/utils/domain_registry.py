from ..domains.admin_api import AdminAPI
from ..domains.attempts_api import AttemptsAPI
from ..domains.auth_api import AuthAPI
from ..domains.exams_api import ExamsAPI
from ..domains.import_export_api import ImportExportAPI
from ..domains.live_exams_api import LiveExamsAPI
from ..domains.log_registry_api import LogRegistryAPI
from ..domains.questions_api import QuestionsAPI
from ..domains.statistics_api import StatisticsAPI
from ..domains.system_api import SystemAPI
from ..domains.user_api import UserAPI


REGISTERED_DOMAIN_APIS = (
    AdminAPI,
    AttemptsAPI,
    AuthAPI,
    ExamsAPI,
    ImportExportAPI,
    LiveExamsAPI,
    LogRegistryAPI,
    QuestionsAPI,
    StatisticsAPI,
    SystemAPI,
    UserAPI,
)


def discover_domain_api_classes(package_name="app.web_server.api_m.domains"):
    # Keep the public function shape stable, but use explicit imports so
    # frozen desktop builds do not depend on runtime module discovery.
    return list(REGISTERED_DOMAIN_APIS)


def register_domain_apis(app, user_manager, db_manager, service_manager, package_name="app.web_server.api_m.domains"):
    registered_names = []
    for api_class in discover_domain_api_classes(package_name):
        api_class(app, user_manager, db_manager, service_manager).register()
        registered_names.append(api_class.__name__)
    return registered_names
