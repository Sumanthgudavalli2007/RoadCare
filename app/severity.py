
def estimate_severity(notes):
    """
    Initial rule-based estimate using report notes.
    This is not a trained AI image classifier.
    """
    text = (notes or "").lower()

    high_keywords = [
        "deep pothole",
        "very deep",
        "large pothole",
        "major damage",
        "accident",
        "dangerous",
        "road collapsed",
    ]

    low_keywords = [
        "small crack",
        "minor crack",
        "slight damage",
        "small pothole",
    ]

    if any(keyword in text for keyword in high_keywords):
        return "High"

    if any(keyword in text for keyword in low_keywords):
        return "Low"

    return "Medium"
