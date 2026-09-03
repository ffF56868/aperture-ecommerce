from django.test import TestCase

from apps.after_sales.evaluation import AfterSalesAgentEvaluator, build_agent_eval_cases
from apps.after_sales.models import (
    AfterSalesCase,
    AgentConversation,
    AgentEvaluationCaseResult,
    AgentEvaluationRun,
    ConfirmationRequest,
    ToolExecution,
)


class AfterSalesAgentEvaluationTests(TestCase):
    def test_checked_in_suite_has_twenty_distinct_cases(self):
        cases = build_agent_eval_cases()

        self.assertEqual(len(cases), 20)
        self.assertEqual(len({case.case_id for case in cases}), 20)

    def test_deterministic_replay_eval_passes_and_rolls_back_its_fixture_data(self):
        report = AfterSalesAgentEvaluator().run()
        data = report.as_dict()

        self.assertEqual(data["summary"], {"total": 20, "passed": 20, "failed": 0})
        self.assertTrue(all(item["passed"] for item in data["cases"]))
        self.assertEqual(data["metrics"]["intent_recognition"]["rate"], 100.0)
        self.assertEqual(data["metrics"]["tool_selection"]["rate"], 100.0)
        self.assertEqual(data["metrics"]["parameter_correctness"], {
            "passed": 15,
            "total": 15,
            "failed": 0,
            "rate": 100.0,
        })
        self.assertEqual(data["metrics"]["unauthorized_interception"]["rate"], 100.0)
        self.assertEqual(data["metrics"]["dangerous_interception"]["rate"], 100.0)
        self.assertEqual(data["metrics"]["human_handoff"]["passed"], 2)
        self.assertEqual(data["metrics"]["failure"]["rate"], 0.0)
        self.assertTrue(data["evaluation_run_id"])
        self.assertEqual(AgentEvaluationRun.objects.count(), 1)
        self.assertEqual(AgentEvaluationCaseResult.objects.count(), 20)
        self.assertEqual(AgentConversation.objects.count(), 0)
        self.assertEqual(ConfirmationRequest.objects.count(), 0)
        self.assertEqual(AfterSalesCase.objects.count(), 0)
        self.assertEqual(ToolExecution.objects.count(), 0)
