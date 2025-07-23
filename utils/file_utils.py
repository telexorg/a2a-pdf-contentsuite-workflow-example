import base64
import os

def save_base64_to_file(base64_str: str, output_path: str) -> None:
    """
    Saves a base64-encoded string to a file.

    Args:
        base64_str (str): The base64 string (with or without data URI prefix).
        output_path (str): Path where the decoded file should be saved.
    """
    # If data URI prefix is present, strip it
    if base64_str.startswith("data:"):
        base64_str = base64_str.split(",", 1)[-1]

    try:
        file_data = base64.b64decode(base64_str)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(file_data)
        print(f"[✓] File saved to {output_path}")
    except Exception as e:
        print(f"[✗] Failed to save file: {e}")
