import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from pydantic import ValidationError

from venmo_lunchmoney_ai.matching import (
    MODEL,
    ReimbursementMatch,
    ReimbursementMatches,
    match_reimbursements,
)


class MatchReimbursementsTest(unittest.TestCase):
    def test_uses_current_model_and_structured_output(self):
        messages = [
            {"role": "system", "content": "Match reimbursements"},
            {"role": "user", "content": "transaction_id,amount"},
        ]
        matches = ReimbursementMatches(
            groups=[
                ReimbursementMatch(
                    transaction_id=10,
                    matches=[20],
                    missing_reimbursements=False,
                    confidence=0.9,
                    confidence_reason="The payee and amount match",
                )
            ]
        )
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(output_parsed=matches)

        result = match_reimbursements(client, messages)

        self.assertEqual(result, matches.groups)
        client.responses.parse.assert_called_once_with(
            model=MODEL,
            input=messages,
            text_format=ReimbursementMatches,
        )

    def test_rejects_response_without_parsed_output(self):
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(output_parsed=None)

        with self.assertRaisesRegex(ValueError, "did not contain reimbursement matches"):
            match_reimbursements(client, [])

    def test_rejects_confidence_outside_expected_range(self):
        with self.assertRaises(ValidationError):
            ReimbursementMatch(
                transaction_id=10,
                matches=[20],
                missing_reimbursements=False,
                confidence=1.1,
                confidence_reason="Invalid confidence",
            )


if __name__ == "__main__":
    unittest.main()
