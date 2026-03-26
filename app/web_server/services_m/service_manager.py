from pathlib import Path

from support_m import get_runtime_config

from .connection_info_service import ConnectionInfoService
from .exam_attempt_service import AttemptService, LiveExamService
from .log_registry_service import LogRegistryService
from .package_service import PackageService
from .question_logic_service import QuestionLogicService


class ServiceManager:
    def __init__(self, db_manager, project_root=None, media_root=None, runtime_config=None):
        config = dict(runtime_config or get_runtime_config())

        self.db = db_manager
        self.project_root = Path(project_root or config["app_root"]).resolve()
        self.media_root = Path(media_root or config["media_root"]).resolve()
        self.runtime_config = config

        self.question_logic = QuestionLogicService()
        self.log_registry = LogRegistryService(self.db)
        self.attempts = AttemptService(self.db, question_logic=self.question_logic)
        self.live_exams = LiveExamService(self.db, attempt_service=self.attempts)
        self.packages = PackageService(
            self.db,
            self.project_root,
            media_root=self.media_root,
            log_registry=self.log_registry,
        )
        self.connection_info = ConnectionInfoService(self.db, runtime_config=self.runtime_config)
