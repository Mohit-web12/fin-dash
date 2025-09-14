# backend/services/categorize.py

def categorize(merchant: str) -> tuple[str, str]:
    m = (merchant or "").lower()

    rules = {
        ("uber", "lyft"): ("Transport", "Rideshare"),
        ("starbucks", "dunkin", "peet"): ("Dining", "Coffee"),
        ("chipotle", "mcdonald", "taco"): ("Dining", "Fast Food"),
        ("whole foods", "trader joe", "kroger", "stop & shop"): ("Groceries", "Supermarket"),
        ("netflix", "spotify", "hulu"): ("Subscriptions", "Entertainment"),
        ("verizon", "t-mobile", "att"): ("Utilities", "Phone"),
        ("coned", "pseg", "national grid"): ("Utilities", "Electric/Gas"),
        ("amazon",): ("Shopping", "Online"),
        ("doordash", "ubereats", "grubhub"): ("Dining", "Delivery"),
        ("shell", "bp", "mobil", "exxon"): ("Transport", "Gas"),
        ("walmart", "target", "costco"): ("Shopping", "Retail"),
        ("apple", "app store"): ("Subscriptions", "Apps"),
    }

    for keys, cat in rules.items():
        if any(k in m for k in keys):
            return cat

    return ("Uncategorized", "Other")
