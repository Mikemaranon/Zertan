import sys
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(WEB_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_SERVER_ROOT))


@dataclass
class ModuleExecutionResult:
    name: str
    tests_run: int
    failures: int
    errors: int

    @property
    def successful(self):
        return self.failures == 0 and self.errors == 0


@dataclass
class DomainExecutionResult:
    name: str
    module_results: list

    @property
    def tests_run(self):
        return sum(result.tests_run for result in self.module_results)

    @property
    def failures(self):
        return sum(result.failures for result in self.module_results)

    @property
    def errors(self):
        return sum(result.errors for result in self.module_results)

    @property
    def successful(self):
        return self.failures == 0 and self.errors == 0


def run_test_module(module_name, *, verbosity=2):
    suite = unittest.defaultTestLoader.loadTestsFromName(module_name)
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    return ModuleExecutionResult(
        name=module_name,
        tests_run=result.testsRun,
        failures=len(result.failures),
        errors=len(result.errors),
    )


def run_domain(domain_name, module_runners):
    print(f"\n== Domain: {domain_name} ==")
    module_results = []
    for label, runner in module_runners:
        print(f"\n-- {label} --")
        module_results.append(runner())
    summary = DomainExecutionResult(domain_name, module_results)
    print(
        f"\n== Summary: {domain_name} | tests={summary.tests_run} "
        f"failures={summary.failures} errors={summary.errors} =="
    )
    return summary


def exit_code_from_results(domain_results):
    return 0 if all(result.successful for result in domain_results) else 1
