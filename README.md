## Venmo Lunchmoney AI Tool

> [!IMPORTANT]
> This is still a work in progress!

This is a small tool that uses GPT-4 to try and match one or many Venmo
reimbursement transactions in [Lunch Money](https://lunchmoney.app/) to the transaction that is being reimbursed.

This tool pairs very well with
[venmo-auto-cashout](https://github.com/evanpurkhiser/venmo-auto-cashout)

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
