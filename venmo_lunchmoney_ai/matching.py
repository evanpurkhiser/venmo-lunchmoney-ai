from openai import OpenAI
from pydantic import BaseModel, Field

MODEL = "gpt-5.6-sol"


class ReimbursementMatch(BaseModel):
    transaction_id: int
    matches: list[int]
    missing_reimbursements: bool
    confidence: float = Field(ge=0, le=1)
    confidence_reason: str


class ReimbursementMatches(BaseModel):
    groups: list[ReimbursementMatch]


def match_reimbursements(
    client: OpenAI,
    messages: list[dict[str, str]],
) -> list[ReimbursementMatch]:
    response = client.responses.parse(
        model=MODEL,
        input=messages,
        text_format=ReimbursementMatches,
    )

    if response.output_parsed is None:
        raise ValueError("OpenAI response did not contain reimbursement matches")

    return response.output_parsed.groups
