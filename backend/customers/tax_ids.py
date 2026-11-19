"""Brazilian tax IDs: CPF (individuals) and CNPJ (companies), including alphanumeric CNPJ.

Since July 2026 the Federal Revenue issues alphanumeric CNPJs: the first 12 characters may be
letters or digits and the last 2 (check digits) are always digits. Each character's value is
its ASCII code minus 48, which keeps the classic numeric CNPJ valid under the same algorithm.
"""

import re

_NON_ALNUM = re.compile(r"[^0-9A-Za-z]")
_CNPJ = re.compile(r"^[0-9A-Z]{12}[0-9]{2}$")
_CPF = re.compile(r"^[0-9]{11}$")


def normalize_tax_id(value: str) -> str:
    """Remove punctuation/spaces and uppercase: '12.abc.345/01de-35' -> '12ABC34501DE35'."""
    return _NON_ALNUM.sub("", value or "").upper()


def _check_digit(values: list[int], weights: list[int]) -> int:
    remainder = sum(v * w for v, w in zip(values, weights, strict=True)) % 11
    return 0 if remainder < 2 else 11 - remainder


def is_valid_cpf(value: str) -> bool:
    cpf = normalize_tax_id(value)
    if not _CPF.match(cpf) or len(set(cpf)) == 1:
        return False
    digits = [int(c) for c in cpf]
    first = _check_digit(digits[:9], list(range(10, 1, -1)))
    second = _check_digit(digits[:10], list(range(11, 1, -1)))
    return digits[9:] == [first, second]


def is_valid_cnpj(value: str) -> bool:
    cnpj = normalize_tax_id(value)
    if not _CNPJ.match(cnpj) or len(set(cnpj)) == 1:
        return False
    values = [ord(c) - 48 for c in cnpj]
    weights = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    first = _check_digit(values[:12], weights[1:])
    second = _check_digit(values[:13], weights)
    return values[12:] == [first, second]


def brazilian_tax_id_kind(value: str) -> str | None:
    """'cpf', 'cnpj' or None when the value is not a valid Brazilian tax ID."""
    normalized = normalize_tax_id(value)
    if len(normalized) == 11 and is_valid_cpf(normalized):
        return "cpf"
    if len(normalized) == 14 and is_valid_cnpj(normalized):
        return "cnpj"
    return None
