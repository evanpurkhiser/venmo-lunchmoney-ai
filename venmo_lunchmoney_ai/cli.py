import argparse
import json
import logging
from datetime import datetime, timedelta
from os import getenv

import openai
from lunchable import LunchMoney

from venmo_lunchmoney_ai.grouping import create_lunchmoney_group
from venmo_lunchmoney_ai.prompt import build_prompt_messages
from venmo_lunchmoney_ai.types import ReimbursmentGroup

CUTOFF_DAYS = 60
"""
How many days worth of transactions should we look back. We're only included
unreviewed transactions, so this can be a very large number.

This only needs to be as high as how long we might expect for someone to
"delay" sending in a venmo reimbursement for something.
"""

logger = logging.getLogger(__name__)


def run_cli():
    parser = argparse.ArgumentParser(
        description="Automatically cash-out your Venmo balance as individual transfers"
    )

    parser.add_argument(
        "-v",
        "--verbose",
        help="increase output verbosity",
        action="store_true",
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
        default=getenv("VENMO_CATEGORY"),
        help="The category which contains un-sorted venmo transactions",
    )
    parser.add_argument(
        "--reimbursed-category",
        type=str,
        default=getenv("REIMBURSED_CATEGORY"),
        help="The category that grouped reimbursments will become a part of",
    )

    parser.add_argument(
        "--reimbursement-tag",
        type=str,
        default=getenv("REIMBURSEMENT_TAG"),
        help="The name of the tag which marks transactions pending venmo reimbursements",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    lunch = LunchMoney(access_token=args.lunchmoney_token)
    openai.api_key = args.openai_token

    categories = lunch.get_categories()
    try:
        venmo_category = next(c for c in categories if c.name == args.venmo_category)
    except StopIteration:
        logger.error(f"Cannot find Lunch Money category {args.venmo_category}")
        return

    try:
        reimbursed_category = next(c for c in categories if c.name == args.reimbursed_category)
    except StopIteration:
        logger.error(f"Cannot find Lunch Money category {args.reimbursed_category}")
        return

    tags = lunch.get_tags()
    try:
        reimbursement_tag = next(t for t in tags if t.name == args.reimbursement_tag)
    except StopIteration:
        logger.error(f"Cannot find Lunch Money tag {args.reimbursement_tag}")
        return

    # Reduce the transaction to just candidate transactions. These transactions
    # match the follwoing criteria
    #
    # - Venmo reimbursement transactions (amount is income)
    # - Transactions marked with the reimbursement-tag
    #
    transactions = [
        transaction
        for transaction in lunch.get_transactions(
            status="uncleared",
            start_date=datetime.now() - timedelta(days=CUTOFF_DAYS),
            end_date=datetime.now(),
        )
        if
        # Ignore venmo expense transactions
        not (transaction.category_id == venmo_category.id and transaction.amount > 0)
        # Ingore transactions not marked with the reimbursement-tag
        and not (
            transaction.category_id != venmo_category.id
            and not any(t for t in (transaction.tags or []) if t.id == reimbursement_tag.id)
        )
    ]

    logger.info(f"Got {len(transactions)} candidate transactions from Lunchmoney")

    venmos = [t for t in transactions if t.category_id == venmo_category.id]
    main_transactions = [t for t in transactions if t.category_id != venmo_category.id]

    # Nothing to do if we have no venmo transactions
    if not venmos:
        logger.info("No transactions in the Venmo category, nothing to do.")
        return

    # Nothing to do if we have no transactions marked as pending venmos
    if not main_transactions:
        logger.info("No transactions pending venmo reimbursements, nothing to do.")
        return

    transactions_map = {t.id: t for t in transactions}

    messages = build_prompt_messages(venmo_category.name, categories, transactions)

    # Ask chat GPT how to group venmo transactions
    response = openai.ChatCompletion.create(model="gpt-4", messages=messages)

    try:
        assert isinstance(response, dict)
        json_response = json.loads(response["choices"][0]["message"]["content"])
    except:
        logger.warn("Unexpected GPT-4 response", extra={"response": response})
        return

    groups = [
        ReimbursmentGroup(
            transaction=transactions_map[data["transaction_id"]],
            matches=[transactions_map[id] for id in data["matches"]],
            missing_reimbursements=data["missing_reimbursements"],
            confidence=data["confidence"],
            confidence_reason=data["confidence_reason"],
        )
        for data in json_response
    ]

    for group in groups:
        if not group.missing_reimbursements:
            create_lunchmoney_group(lunch, reimbursed_category, group)

        print("")
        print(f"{group.transaction.payee} (${group.transaction.amount})")
        for venmo in group.matches:
            print(f" -> {venmo.payee} paid ${abs(venmo.amount)} [note: {venmo.notes}]")

        print(f" -> (you paid ${group.you_pay})")
        print(f" ??: {group.confidence_reason}")

        if group.missing_reimbursements:
            print(f" !!: Pending additional reimbursements")
