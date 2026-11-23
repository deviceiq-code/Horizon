"""Expected lists pasted from a spreadsheet (pure parsing, tested).

Columns: model ("Manufacturer Model", or the model alone when only one manufacturer has it),
serial number (optional) and quantity (optional, 1 by default; 1 when there is a serial).
Cells are separated by tabs (copied from a spreadsheet), semicolons or commas; a first line
that names the columns is skipped.
"""

import re
from dataclasses import dataclass

_HEADER_WORDS = {
    "model",
    "modelo",
    "serial",
    "série",
    "serie",
    "quantity",
    "quantidade",
    "cantidad",
}


@dataclass(frozen=True)
class PastedRow:
    line: int
    model_text: str
    serial: str
    quantity: int | None  # None: not a valid whole number ≥ 1
    quantity_text: str


def _cells(line: str) -> list[str]:
    for separator in ("\t", ";", ","):
        if separator in line:
            return [cell.strip() for cell in line.split(separator)]
    return [line.strip()]


def parse_pasted(text: str) -> list[PastedRow]:
    rows: list[PastedRow] = []
    for number, raw in enumerate((text or "").splitlines(), start=1):
        if not raw.strip():
            continue
        cells = _cells(raw) + ["", ""]
        model_text, serial, quantity_text = cells[0], cells[1], cells[2]
        if number == 1 and model_text.casefold() in _HEADER_WORDS:
            continue
        serial = "".join(serial.split()).upper()
        quantity: int | None
        if not quantity_text:
            quantity = 1
        elif re.fullmatch(r"\d+", quantity_text) and int(quantity_text) >= 1:
            quantity = int(quantity_text)
        else:
            quantity = None
        rows.append(
            PastedRow(number, " ".join(model_text.split()), serial, quantity, quantity_text)
        )
    return rows


def model_key(text: str) -> str:
    return " ".join((text or "").split()).casefold()
