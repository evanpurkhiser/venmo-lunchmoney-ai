import csv
import io
from typing import List

from lunchable.models import CategoriesObject, TransactionObject

PROMPT = """
You are given a CSV of my personal bank transactions. Positive amounts are
income, negative are expenses. Match transactions in the `{category}` category
to any other  transaction that is not in the `{category}` category. It is
possible that many `{category}` transactions match one main transaction. Once a
`{category}` transaction becomes part of a main transaction group, it should
not be part of any other groups. Use the `notes` column of the `{category}`
transaction to try to match the `payee` of candidate transactions.

A `{category}` transaction is a reimbursement from a friend because I paid for
something. Example:

```csv
transaction_id,category,payee,amount,notes,original_name
242330919,{category},Eric,6,"Thanks for Boba Guys",Venmo
242330918,Snack,"Boba Guys",-12,"Waiting on Eric",BOBAGUYS
242330917,Gas,"BP Gas",-24,"Waiting on Ryan",BP
```

In the example, I paid for "Boba Guys". Eric then reimbursed me $6 for his
portion. We have HIGH confidence these match since it is an even split of the
cost of my item and his item and the note mentions "Waiting on Eric".

In some cases, the reimbursements may not perfectly divide into the main
transaction amount, my portion may have been more or less. In MOST cases a
portion of the main transaction is something I myself paid for. There may be
cases where I pay for something, and the entire cost is covered by `{category}`
transactions, though it is rare.

Main transactions must ALWAYS included a note that either mentions the names of
the people I expect to reimburse me for the transaction OR the number of
reimbursements I expect. We calculate a `missing_reimbursements` boolean. For
example if a transaction specifies we're waiting on Eric, Randolf, and Joe, but
there is only a `{category}` reimbursement from Randolf, then the value is
true. If a note containing this information is missing do not include this
transaction group in your response.

Be aware, the `notes` column for `{category}` transactions is user input from
the friend reimbursing me, so will not usually perfectly match the payee name.
If it does perfectly match then we have a very high confidence.

Your output for this example is as follows.

```json
[
  {{
    "transaction_id": 242330918,
    "matches": [242330919],
    "missing_reimbursements": false,
    "confidence": 0.9,
    "confidence_reason": "Amount evently divides and exact payee name is in the note"
  }}
]
```

- Note that the schema will ALWAYS match the above data types.
- The `confidence_reason` should describe WHY the matched `{category}`
  transactions were included in the group, please be specific.

- Main transactions for matching should not belong to the `{category}`
  category.
- ONLY include main transactions that have matching `{category}` transactions.
- It is possible that the list of transactions has no groups of main
  transactions with matching `{category}` transactions.
- It is possible that `{category}` transactions may not belong to a group in
  that case that someone is paying me for something they bought from me, not
  reimbursing me.

From the following CSV please produce a mapping of regular transactions to the
one or many `{category}` transactions. Please also include a confidence score
between 0 and 1 per group of transactions, this can be calculated based on how
closely the `notes` match the main transaction `payee` as well as how evenly
the `{category}` transactions divide into the main transaction. Only include
items that have at least a `0.4` confidence score.

**IMPORTANT**: Please ONLY provide the response in machine-readable JSON
format. No explanations, no clarifications, and no additional context. Simply
output the valid JSON based on the data provided.

**DO NOT write code**, you are doing the actual matching.
"""


def table_to_csv_string(table):
    output = io.StringIO()
    fieldnames = table[0].keys() if table else []

    csv_writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
        quoting=csv.QUOTE_NONNUMERIC,
    )
    csv_writer.writeheader()

    for row in table:
        csv_writer.writerow(row)

    return output.getvalue()


def build_prompt_messages(
    category: str,
    categories: List[CategoriesObject],
    transaction_list: List[TransactionObject],
):
    category_map = {c.id: c.name for c in categories}
    table = [
        {
            "transaction_id": t.id,
            "category": category_map.get(t.category_id or 0, None),
            "payee": t.payee,
            "amount": t.amount,
            "notes": t.notes,
            "original_name": t.original_name,
        }
        for t in transaction_list
        if t.group_id is None
    ]

    system_prompt = PROMPT.format(category=category)
    csv_table = table_to_csv_string(table)

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": csv_table},
    ]
