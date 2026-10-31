"""SD-1: exact byte quantities; relative input only with an explicit base."""
import re
from decimal import Decimal

SUFFIXES = {"B": 1, "KiB": 2**10, "MiB": 2**20, "GiB": 2**30,
            "TiB": 2**40, "KB": 1000, "MB": 10**6, "GB": 10**9,
            "TB": 10**12, "G": 2**30}


def parse(value: str, *, current: int | None = None) -> int:
    relative = value.startswith("+")
    if relative:
        if current is None:
            raise ValueError("+SIZE is accepted only by can-upscale --memory")
        value = value[1:]
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(KiB|MiB|GiB|TiB|KB|MB|GB|TB|B|G)", value)
    if match is None:
        raise ValueError("size requires a suffix: " + ", ".join(SUFFIXES))
    amount = Decimal(match[1]) * SUFFIXES[match[2]]
    if amount != amount.to_integral_value():
        raise ValueError("size must resolve to whole bytes")
    return int(amount) + (current if relative else 0)


def format_gib(value: int) -> str:
    return f"{Decimal(value) / 2**30:.2f} GiB"
