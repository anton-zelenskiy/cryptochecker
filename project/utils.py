def get_currency_prices_display(data: dict) -> str:
    """Wraps info in html tags."""
    rows = []
    for code, price in data.items():
        rows.append(f"<i>{code.upper()}</i>: <b>{price}$</b>")

    return '\n'.join(rows)
