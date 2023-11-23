## Venmo Lunchmoney AI Tool

> [!IMPORTANT]
> This is still a work in progress!

This is a small tool that uses GPT-4 to try and match one or many Venmo
reimbursement transactions in [Lunchmoney](https://lunchmoney.app/) to the
transaction that is being reimbursed.

```
$ venmo-lunchmoney-ai

El Lopo ($60.0)
 -> Venmo Received paid $30.0 [note: Erika: El Lopo wine bar]
 -> (you paid $30.0)
 ?? Amount evenly divides and partial payee name is in the note

Mos Grill Inc ($55.76)
 -> Venmo Received paid $27.88 [note: Josh: Mos Burger]
 -> (you paid $27.88)
 ?? Amount evenly divides and exact payee name is in the note

Ramen Nagi ($60.76)
 -> Randolf paid $20.26 [note: Ramen Nagi]
 -> Eric paid $20.25 [note: Ramen Nagi]
 -> (you paid $20.25)
 ?? Amount evenly divides and exact payee name is in the note
```

### Workflow requirements

This tool is intended to be run on a crontab where it will automatically handle
grouping transactions, becuase of this there are some workflow constraints that
need to be followed to avoid large spend on OpenAI API calls.

1. You will need to be using something like
   [Venmo-auto-cashout](https://github.com/evanpurkhiser/venmo-auto-cashout) to
   create individual transactions within Lunchmoney for every incoming Venmo
   transaction. This tool cannot split large Venmo bank transfers, it has no
   knowledge of the Venmo transactions themselves, only venmo transactions
   within Lunchmoney.

   GPT-4 may use the names and notes of the Venmo transactions to help
   understand where to match those transactions, so it's ideal that that
   metadata is included in the Lunchmoney transactions.

2. Transactions that are being reimbursed MUST be marked with a specific tag
   (specified by `--reimbursement-tag`) to indicate to the tool that a
   transaction should be considered for matching.

   > [!NOTE]  
   > Only transactions with the `reimbursement-tag` and Vemmo income
   > transactions will be sent to OpenAI.

3. For transactions marked with the `reimbursement-tag` you MUST specify either
   the names of who you expect to receive Venmo reimbursements from OR the
   number of people you expect to reimburse you in the transaction notes.
   Transactions without notes will NOT be considered.

   You can put the "real note" in brackets like `[real note here]` to have the
   final split transaction include this note.

   We do this to allow GPT-4 to understand if a transaction is still waiting
   for more transactions to appear.

### Efficiency

The tool maintains state in the `--history-db` of previously processed
transactions. During each run the tool will ONLY talk to GPT-4 when the
list of transactions queried from Lunch money is different from the previously
un grouped transaction list.

This means we will only talk to GPT-4 when we have new information to attempt
to match transactions
