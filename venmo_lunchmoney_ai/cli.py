import argparse
from os import getenv


def run_cli():
    parser = argparse.ArgumentParser(
        description="Automatically cash-out your Venmo balance as individual transfers"
    )

    parser.add_argument(
        "--quiet", action=argparse.BooleanOptionalAction, help="Do not produce any output"
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
        default=getenv("LUNCHMONEY_CATEGORY"),
        help="The category which contains un-sorted venmo transactions",
    )

    args = parser.parse_args()

    print("TESTING!")
