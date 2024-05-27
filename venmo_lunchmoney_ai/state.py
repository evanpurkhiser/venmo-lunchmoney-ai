import json


def get_prev_unprocessed_transactions(file: str) -> list[int]:
    try:
        with open(file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def set_prev_unprocessed_transactions(file: str, transaction_ids: list[int]):
    with open(file, "w") as f:
        json.dump(transaction_ids, f)
