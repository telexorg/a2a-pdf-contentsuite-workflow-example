def parse_tts_options(user_input: str) -> dict:
    options = {"voice_name": "Kore"}
    input_lower = user_input.lower()

    if "alloy" in input_lower:
        options["voice_name"] = "Alloy"
    elif "echo" in input_lower:
        options["voice_name"] = "Echo"
    elif "fable" in input_lower:
        options["voice_name"] = "Fable"
    elif "onyx" in input_lower:
        options["voice_name"] = "Onyx"
    elif "nova" in input_lower:
        options["voice_name"] = "Nova"
    elif "shimmer" in input_lower:
        options["voice_name"] = "Shimmer"
    elif "kore" in input_lower:
        options["voice_name"] = "Kore"
    elif "male" in input_lower or "man" in input_lower:
        options["voice_name"] = "Onyx"
    elif "female" in input_lower or "woman" in input_lower:
        options["voice_name"] = "Nova"

    return options
