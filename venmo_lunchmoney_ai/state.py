import json
from typing import List


def get_prev_unprocessed_transactions(file: str) -> List[int]:
    try:
        with open(file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def set_prev_unprocessed_transactions(file: str, transaction_ids: List[int]):
    with open(file, "w") as f:
        json.dump(transaction_ids, f)
