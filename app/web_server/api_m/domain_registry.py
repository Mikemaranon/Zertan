from api_m.domains.admin_api import AdminAPI
from api_m.domains.attempts_api import AttemptsAPI
from api_m.domains.auth_api import AuthAPI
from api_m.domains.exams_api import ExamsAPI
from api_m.domains.import_export_api import ImportExportAPI
from api_m.domains.live_exams_api import LiveExamsAPI
from api_m.domains.questions_api import QuestionsAPI
from api_m.domains.statistics_api import StatisticsAPI
from api_m.domains.system_api import SystemAPI
from api_m.domains.user_api import UserAPI


REGISTERED_DOMAIN_APIS = (
    AdminAPI,
    AttemptsAPI,
    AuthAPI,
    ExamsAPI,
    ImportExportAPI,
    LiveExamsAPI,
    QuestionsAPI,
    StatisticsAPI,
    SystemAPI,
    UserAPI,
)


def discover_domain_api_classes(package_name="api_m.domains"):
    # Keep the public function shape stable, but use explicit imports so
    # frozen desktop builds do not depend on runtime module discovery.
    return list(REGISTERED_DOMAIN_APIS)


def register_domain_apis(app, user_manager, db_manager, service_manager, package_name="api_m.domains"):
    registered_names = []
    for api_class in discover_domain_api_classes(package_name):
        api_class(app, user_manager, db_manager, service_manager).register()
        registered_names.append(api_class.__name__)
    return registered_names
