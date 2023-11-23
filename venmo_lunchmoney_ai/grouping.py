from lunchable import LunchMoney
from lunchable.models import CategoriesObject, TransactionSplitObject

from venmo_lunchmoney_ai.types import ReimbursmentGroup


def split_transaction(
    lunch: LunchMoney,
    reimbursed_category: CategoriesObject,
    group: ReimbursmentGroup,
):
    """
    Splits the main transaction into two transactions, the portiona paid by me
    and the portion that is being reimbursed by the venmo transactions
    """
    split_objects = [
        # Reimbursment venmos
        TransactionSplitObject(
            date=group.transaction.date,
            category_id=reimbursed_category.id,
            notes="",
            amount=float(group.they_pay),
        ),
        # The portion paid by me
        TransactionSplitObject(
            date=group.transaction.date,
            category_id=group.transaction.category_id,
            notes=group.main_note,
            amount=float(group.you_pay),
        ),
    ]

    resp = lunch.update_transaction(
        transaction_id=group.transaction.id,
        split=split_objects,
    )

    # Get the transaction objects we just split
    transactions = [lunch.get_transaction(id) for id in resp["split"]]

    # Get the transaction that we're going to group
    return next(t for t in transactions if t.category_id == reimbursed_category.id)


def create_lunchmoney_group(
    lunch: LunchMoney,
    reimbursed_category: CategoriesObject,
    group: ReimbursmentGroup,
):
    """
    Splits the main transaction and groups the reimbursement transactions
    """
    # If I do not owe anything, we can simply group the venmos directly with
    # the main transaction
    if group.you_pay == 0:
        target_transaction = group.transaction
    else:
        target_transaction = split_transaction(lunch, reimbursed_category, group)

    lunch.insert_transaction_group(
        date=group.transaction.date,
        payee=group.transaction.payee or "Venmo Reimbursment",
        category_id=reimbursed_category.id,
        notes=", ".join(m.payee.split()[0] for m in group.matches),
        transactions=[t.id for t in [target_transaction, *group.matches]],
    )
