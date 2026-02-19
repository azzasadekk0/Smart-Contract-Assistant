import unittest
from dataclasses import dataclass

from app.evaluation import evaluate_cases


@dataclass
class FakeCitation:
    source: str


@dataclass
class FakeResponse:
    answer: str
    citations: list[FakeCitation]
    retrieved_contexts: list[str]


class FakeService:
    def __init__(self, responses: dict[str, FakeResponse], failing_questions: set[str] | None = None) -> None:
        self.responses = responses
        self.failing_questions = failing_questions or set()
        self.calls: list[tuple[str, str]] = []

    def answer(self, question: str, session_id: str) -> FakeResponse:
        self.calls.append((question, session_id))
        if question in self.failing_questions:
            raise RuntimeError("forced failure")
        return self.responses[question]


class EvaluationTests(unittest.TestCase):
    def test_evaluation_metrics_include_reliability_signals(self) -> None:
        service = FakeService(
            responses={
                "Who are the parties?": FakeResponse(
                    answer="The supplier and distributor are the two parties.",
                    citations=[FakeCitation("3707e488749344c49ff61e6449a067db_FuseMedicalInc.pdf")],
                    retrieved_contexts=["The supplier and distributor are the parties in this agreement."],
                ),
                "What is the order timeline?": FakeResponse(
                    answer="Orders are accepted within 7 business days and fulfilled in 7 business days.",
                    citations=[FakeCitation("GentechHoldingsInc.pdf")],
                    retrieved_contexts=["Orders must be accepted within 7 business days and fulfilled in 7 business days."],
                ),
            }
        )

        cases = [
            {
                "question": "Who are the parties?",
                "expected_answer": "The parties are a supplier and a distributor.",
                "required_terms": ["supplier", "distributor"],
                "forbidden_terms": ["not enough evidence"],
                "expected_sources": ["FuseMedicalInc.pdf"],
            },
            {
                "question": "What is the order timeline?",
                "expected_answer": "Orders are accepted and fulfilled within 7 business days.",
                "required_terms": ["accepted", "fulfilled", "7 business days"],
                "forbidden_terms": ["unknown"],
                "expected_sources": ["GentechHoldingsInc.pdf"],
            },
        ]

        metrics = evaluate_cases(service, cases)

        self.assertIn("answer_f1", metrics)
        self.assertIn("source_recall", metrics)
        self.assertIn("source_precision", metrics)
        self.assertIn("required_term_coverage", metrics)
        self.assertIn("valid_case_rate", metrics)
        self.assertIn("success_rate", metrics)

        self.assertEqual(metrics["valid_case_rate"], 1.0)
        self.assertEqual(metrics["success_rate"], 1.0)
        self.assertEqual(metrics["retrieval_hit_rate"], 1.0)
        self.assertEqual(metrics["source_recall"], 1.0)
        self.assertEqual(metrics["source_precision"], 1.0)
        self.assertEqual(metrics["forbidden_term_violation_rate"], 0.0)
        self.assertGreater(metrics["answer_f1"], 0.0)
        self.assertGreater(metrics["groundedness"], 0.0)

        session_ids = [session_id for _, session_id in service.calls]
        self.assertEqual(len(session_ids), len(set(session_ids)))
        self.assertTrue(all(sid.startswith("evaluation-") for sid in session_ids))

    def test_evaluation_handles_invalid_and_failed_cases(self) -> None:
        service = FakeService(
            responses={
                "ok question": FakeResponse(
                    answer="Hello contract.",
                    citations=[],
                    retrieved_contexts=["Hello contract."],
                ),
                "failing question": FakeResponse(
                    answer="Should not be used.",
                    citations=[],
                    retrieved_contexts=[],
                ),
            },
            failing_questions={"failing question"},
        )

        cases = [
            {"question": ""},
            {"bad": "shape"},
            {"question": "failing question", "expected_answer": "hello"},
            {"question": "ok question", "expected_answer": "hello contract"},
        ]

        metrics = evaluate_cases(service, cases)

        self.assertEqual(metrics["valid_case_rate"], 0.5)  # 2/4 are structurally valid
        self.assertEqual(metrics["success_rate"], 0.5)  # 1/2 valid cases executed successfully
        self.assertGreaterEqual(metrics["answer_overlap"], 0.0)
        self.assertGreaterEqual(metrics["groundedness"], 0.0)


if __name__ == "__main__":
    unittest.main()
