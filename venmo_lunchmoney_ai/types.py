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
