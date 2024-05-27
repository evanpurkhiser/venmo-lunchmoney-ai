import json


def get_prev_unprocessed_transactions(file: str) -> set[int]:
    try:
        with open(file, "r") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()


def set_prev_unprocessed_transactions(file: str, transaction_ids: list[int]):
    with open(file, "w") as f:
        json.dump(transaction_ids, f)
