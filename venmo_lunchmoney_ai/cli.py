import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import logging
from os import getenv
from typing import List

import openai
from lunchable import LunchMoney

from venmo_lunchmoney_ai.prompt import build_promp_messages


CUTOFF_DAYS = 60
"""
How many days worth of transactions should we look back. We're only included
unreviewed transactions, so this can be high.
"""

logger = logging.getLogger(__name__)


@dataclass
class ReimbursmentGroup:
    transaction_id: int
    """
    The main transaction which money is being reimbursed to
    """
    matches: List[int]
    """
    The transaction IDs of the venmo requests
    """
    confidence: float
    """
    A value between 0 and 1 of how "confident" chat GPT is in the match
    """
    confidence_reason: str
    """
    Chat GPTs reasoning for why it made this match
    """


def run_cli():
    parser = argparse.ArgumentParser(
        description="Automatically cash-out your Venmo balance as individual transfers"
    )

    parser.add_argument(
        "--quiet", action=argparse.BooleanOptionalAction, help="Do not produce any output"
    )
    parser.add_argument(
        "--lunchmoney-token",
        type=str,
        default=getenv("LUNCHMONEY_TOKEN"),
    )
    parser.add_argument(
        "--openai-token",
        type=str,
        default=getenv("OPENAI_TOKEN"),
    )
    parser.add_argument(
        "--venmo-category",
        type=str,
        default=getenv("LUNCHMONEY_CATEGORY"),
        help="The category which contains un-sorted venmo transactions",
    )

    args = parser.parse_args()

    lunch = LunchMoney(access_token=args.lunchmoney_token)
    openai.api_key = args.openai_token

    categories = lunch.get_categories()
    transactions = lunch.get_transactions(
        status="uncleared",
        start_date=datetime.now() - timedelta(days=CUTOFF_DAYS),
        end_date=datetime.now(),
        debit_as_negative=True,
    )

    transactions_map = {t.id: t for t in transactions}

    messages = build_promp_messages(args.venmo_category, categories, transactions)

    # Ask chat GPT how to group venmo transactions
    response = openai.ChatCompletion.create(model="gpt-4", messages=messages)

    if not isinstance(response, dict):
        logging.warn("Did not get expected response from openai")
        return

    groups = [
        ReimbursmentGroup(**data)
        for data in json.loads(response["choices"][0]["message"]["content"])
    ]

    for group in groups:
        main = transactions_map[group.transaction_id]
        venmos = [transactions_map[id] for id in group.matches]

        print("")
        print(f"{main.payee} (${abs(main.amount)})")
        for venmo in venmos:
            print(f" -> {venmo.payee} paid ${abs(venmo.amount)} [note: {venmo.notes}]")

        you_pay = abs(Decimal(str(main.amount)) + sum(Decimal(str(v.amount)) for v in venmos))
        print(f" -> (you paid ${you_pay})")
        print(f" ?? {group.confidence_reason}")
