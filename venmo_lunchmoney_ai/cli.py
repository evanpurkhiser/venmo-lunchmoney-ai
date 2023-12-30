import json
import logging
from datetime import datetime, timedelta
from typing import List

import configargparse
import openai
import sentry_sdk
from lunchable import LunchMoney
from lunchable.models import TransactionObject

from venmo_lunchmoney_ai.grouping import create_lunchmoney_group
from venmo_lunchmoney_ai.notify import notify_telegram
from venmo_lunchmoney_ai.prompt import build_prompt_messages
from venmo_lunchmoney_ai.state import (
    get_prev_unprocessed_transactions,
    set_prev_unprocessed_transactions,
)
from venmo_lunchmoney_ai.types import ReimbursmentGroup

CUTOFF_DAYS = 60
"""
How many days worth of transactions should we look back. We're only included
unreviewed transactions, so this can be a very large number.

This only needs to be as high as how long we might expect for someone to
"delay" sending in a venmo reimbursement for something.
"""

logger = logging.getLogger(__name__)


def parse_args():
    parser = configargparse.ArgParser(
        description="Automatically cash-out your Venmo balance as individual transfers"
    )

    parser.add_argument(
        "-v",
        "--verbose",
        help="increase output verbosity",
        action="store_true",
    )
    parser.add_argument(
        "-d",
        "--dry-run",
        help="Take no actions",
        action="store_true",
    )
    parser.add_argument(
        "--lunchmoney-token",
        type=str,
        required=True,
        env_var="LUNCHMONEY_TOKEN",
    )
    parser.add_argument(
        "--openai-token",
        type=str,
        required=True,
        env_var="OPENAI_TOKEN",
    )
    parser.add_argument(
        "--venmo-category",
        type=str,
        required=True,
        env_var="VENMO_CATEGORY",
        help="The category which contains un-sorted venmo transactions",
    )
    parser.add_argument(
        "--reimbursed-category",
        type=str,
        required=True,
        env_var="REIMBURSED_CATEGORY",
        help="The category that grouped reimbursments will become a part of",
    )
    parser.add_argument(
        "--reimbursement-tag",
        type=str,
        required=True,
        env_var="REIMBURSEMENT_TAG",
        help="The name of the tag which marks transactions pending venmo reimbursements",
    )
    parser.add_argument(
        "--telegram-token",
        type=str,
        required=True,
        env_var="TELEGRAM_TOKEN",
        help="Telegram bot token for notifications",
    )
    parser.add_argument(
        "--telegram-channel",
        type=str,
        required=True,
        env_var="TELEGRAM_CHANNEL",
        help="The telegram channel ID to send notifications to",
    )
    parser.add_argument(
        "--state-file",
        type=str,
        required=True,
        env_var="STATE_FILE",
        help="Used to track previous runs ",
    )

    return parser.parse_args()


def run_cli():
    args = parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    dry_run = args.dry_run

    if dry_run:
        logger.info("Running in dry-run mode. Transactions will not be modified.")

    lunch = LunchMoney(access_token=args.lunchmoney_token)
    openai.api_key = args.openai_token

    # Validate some args
    categories = lunch.get_categories()
    try:
        venmo_category = next(c for c in categories if c.name == args.venmo_category)
        logger.info(f"Found venmo category: {venmo_category.name}")
    except StopIteration:
        logger.error(f"Cannot find Lunchmoney category {args.venmo_category}")
        return

    try:
        reimbursed_category = next(c for c in categories if c.name == args.reimbursed_category)
        logger.info(f"Found reimbursed category: {reimbursed_category.name}")
    except StopIteration:
        logger.error(f"Cannot find Lunchmoney category {args.reimbursed_category}")
        return

    tags = lunch.get_tags()
    try:
        reimbursement_tag = next(t for t in tags if t.name == args.reimbursement_tag)
        logger.info(f"Found reimbursed tag: {reimbursement_tag.name}")
    except StopIteration:
        logger.error(f"Cannot find Lunchmoney tag {args.reimbursement_tag}")
        return

    prev_unprocessed_txns = get_prev_unprocessed_transactions(args.state_file)

    logger.info(f"Previous unprocessed transactions: {prev_unprocessed_txns}")

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
        # Ignore already groupped transactions
        not transaction.group_id
        # Ignore venmo expense transactions
        and not (transaction.category_id == venmo_category.id and transaction.amount > 0)
        # Ingore transactions not marked with the reimbursement-tag
        and not (
            transaction.category_id != venmo_category.id
            and not any(t for t in (transaction.tags or []) if t.id == reimbursement_tag.id)
        )
    ]

    logger.info(f"Got {len(transactions)} candidate transactions from Lunchmoney")

    venmos = [t for t in transactions if t.category_id == venmo_category.id]
    main_transactions = [t for t in transactions if t.category_id != venmo_category.id]

    transacton_ids = set(t.id for t in transactions)

    # Nothing to do if we have no venmo transactions
    if not venmos:
        logger.info("No transactions in the Venmo category, nothing to do.")
        return

    # Nothing to do if we have no transactions marked as pending venmos
    if not main_transactions:
        logger.info("No transactions pending venmo reimbursements, nothing to do.")
        return

    # Nothing to do if we have the same set of transactions from our last run
    if transacton_ids == prev_unprocessed_txns:
        logger.info("Same set of transactions from last run. Nothing to do")
        return

    # Ask chat GPT how to group venmo transactions
    logger.info("Sending prompt to GPT-4...")
    messages = build_prompt_messages(venmo_category.name, categories, transactions)
    response = openai.ChatCompletion.create(model="gpt-4", messages=messages)

    try:
        assert isinstance(response, dict)
        json_response = json.loads(response["choices"][0]["message"]["content"])
    except:
        logger.warn("Unexpected GPT-4 response", extra={"response": response})
        return

    transactions_map = {t.id: t for t in transactions}

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

    # Groups ready to be converted to lunchmoeny groups
    ready_groups = [group for group in groups if group.is_ready]

    # Transactions that were succesffuly converted into lunch money transactions
    successful_transactions: List[TransactionObject] = []

    for group in ready_groups:
        names = [t.payee or "" for t in group.matches]
        logger.info(f"Found group for {group.transaction.payee} {names}")

        try:
            if not dry_run:
                create_lunchmoney_group(lunch, reimbursed_category, group)
            else:
                logger.info("Skipping lunchmoney split in dry-run")
            successful_transactions.extend(group.transactions)
        except Exception as e:
            logger.warn(
                f"Failed to create group for: {group.transaction.payee}",
                exc_info=True,
            )
            sentry_sdk.capture_exception(e)
            continue

        try:
            notify_telegram(group, args.telegram_token, args.telegram_channel)
        except Exception as e:
            logger.warn(
                f"Failed to send telegram notification for: {group.transaction.payee}",
                exc_info=True,
            )
            sentry_sdk.capture_exception(e)
            continue

    # Record what transactions were skippsed. We'll use this during the next
    # run to know if we have new transactions or not.
    skipped_ids = list(transacton_ids - set(t.id for t in successful_transactions))
    logger.info(f"Skipped transactions: {skipped_ids}")

    if not dry_run:
        set_prev_unprocessed_transactions(args.state_file, skipped_ids)
    else:
        logger.info("Not saving skipped transactions to state file in dry-run")
