from review_core.review.prompt import GenerationRequest


def build_dialogue_request(
    *, instructions: str, current_message: str, history: list[str], evidence: list[str]
) -> GenerationRequest:
    return GenerationRequest(
        trusted_instructions=instructions, untrusted_input=(current_message, *history, *evidence)
    )
