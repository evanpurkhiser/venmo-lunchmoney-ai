from dataclasses import dataclass
from decimal import Decimal
from typing import List

from lunchable.models import TransactionObject


@dataclass
class ReimbursmentGroup:
    transaction: TransactionObject
    """
    The main transaction which money is being reimbursed to
    """
    matches: List[TransactionObject]
    """
    The transaction IDs of the venmo requests
    """
    missing_reimbursements: bool
    """
    Indicates that GPT-4 thinks the group is still waiting for additional venmo
    reimbursement transactions to appear
    """
    confidence: float
    """
    A value between 0 and 1 of how "confident" chat GPT is in the match
    """
    confidence_reason: str
    """
    Chat GPTs reasoning for why it made this match
    """

    @property
    def is_ready(self):
        """
        Determines if the transcation group is ready to be processed. If we are
        still missing_reimbursements or the `you_pay` is caluclated as negative
        (GPT failed to match) the transaction is not ready.
        """
        return not self.missing_reimbursements and self.you_pay >= 0

    @property
    def you_pay(self):
        """
        Computes how much was not reimbursed for the transaction
        """
        return Decimal(str(self.transaction.amount)) - self.they_pay

    @property
    def they_pay(self):
        """
        Computes how much was reimbursed for the transaction
        """
        return sum(Decimal(str(abs(match.amount))) for match in self.matches)

    @property
    def transactions(self):
        """
        Retrieve all transactions belonging to this group
        """
        return [self.transaction, *self.matches]
