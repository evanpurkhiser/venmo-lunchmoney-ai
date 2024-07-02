import asyncio

from telegram import Bot
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

from venmo_lunchmoney_ai.types import ReimbursementGroup


def notify_telegram(
    group: ReimbursementGroup,
    token: str,
    channel_id: str,
):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(notify_telegram_async(group, token, channel_id))


async def notify_telegram_async(
    group: ReimbursementGroup,
    token: str,
    channel_id: str,
):
    def e(value: str):
        return escape_markdown(value, version=2)

    header = f"*Venmo Grouped*"
    name = e(f"{group.transaction.payee} (${group.transaction.amount})")
    paid_rows = [
        e(f" → {venmo.payee} paid ${abs(venmo.amount)} [{venmo.notes}]") for venmo in group.matches
    ]

    lines = [
        header,
        name,
        e(group.confidence_reason),
        "",
        "\n".join(paid_rows),
        f" → You paid ${e(str(group.you_pay))}",
    ]

    text = "\n".join(lines)

    await Bot(token).send_message(
        chat_id=channel_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN_V2,
    )
