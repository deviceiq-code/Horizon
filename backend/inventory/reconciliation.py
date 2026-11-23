"""Reconciliation of a receiving lot: what arrived against the expected list (pure, tested).

Rules, per model:
1. Exact matches (model + serial) are fine.
2. An expected serial received under another model → MODEL_MISMATCH.
3. Units without a captured serial (pending or none) stand for expected serial lines of their
   model (the serial is completed at inspection), then fill quantity lines.
4. Units with an unexpected serial fill the model's quantity lines; left over, each one pairs
   with an expected serial line still open → SERIAL_MISMATCH (expected X, received Y).
5. What is still expected → SHORTAGE (one per serial line; one with the missing quantity for
   quantity lines); what still arrived → SURPLUS (one per unit; a model never expected too).
6. Accessories (tracked by quantity): expected quantity × received quantity, the difference
   as SHORTAGE or SURPLUS.
An unscheduled lot (no expected list) has nothing to reconcile.
"""

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Expected:
    model_id: int
    serial: str = ""
    quantity: int = 1


@dataclass(frozen=True)
class ReceivedUnit:
    asset_id: int
    model_id: int
    serial: str = ""  # empty when not captured


@dataclass(frozen=True)
class Finding:
    kind: str  # OccurrenceKind value
    model_id: int
    quantity: int = 1
    expected_serial: str = ""
    received_serial: str = ""
    asset_id: int | None = None


@dataclass
class _Model:
    serial_lines: list[str] = field(default_factory=list)
    quantity: int = 0
    with_serial: list[ReceivedUnit] = field(default_factory=list)
    without_serial: list[ReceivedUnit] = field(default_factory=list)


def _norm(serial: str) -> str:
    return "".join((serial or "").split()).upper()


def reconcile(
    expected: list[Expected],
    units: list[ReceivedUnit],
    accessories: dict[int, int],
    accessory_models: set[int],
) -> list[Finding]:
    """Findings of a lot. `accessories`: received quantity per accessory model;
    `accessory_models`: the models tracked by quantity (their lines compare quantities)."""
    if not expected:
        return []
    findings: list[Finding] = []

    # Accessories: quantities only
    expected_accessories: dict[int, int] = defaultdict(int)
    for line in expected:
        if line.model_id in accessory_models:
            expected_accessories[line.model_id] += line.quantity
    for model_id in sorted(set(expected_accessories) | set(accessories)):
        difference = accessories.get(model_id, 0) - expected_accessories.get(model_id, 0)
        if difference < 0:
            findings.append(Finding("shortage", model_id, quantity=-difference))
        elif difference > 0:
            findings.append(Finding("surplus", model_id, quantity=difference))

    # Units
    models: dict[int, _Model] = defaultdict(_Model)
    for line in expected:
        if line.model_id in accessory_models:
            continue
        if _norm(line.serial):
            models[line.model_id].serial_lines.append(_norm(line.serial))
        else:
            models[line.model_id].quantity += line.quantity
    received = [ReceivedUnit(u.asset_id, u.model_id, _norm(u.serial)) for u in units]

    # 1. Exact matches
    remaining: list[ReceivedUnit] = []
    for unit in received:
        lines = models[unit.model_id].serial_lines if unit.model_id in models else []
        if unit.serial and unit.serial in lines:
            lines.remove(unit.serial)
        else:
            remaining.append(unit)

    # 2. Expected serial under another model
    open_serials = {serial: model_id for model_id, m in models.items() for serial in m.serial_lines}
    leftover: list[ReceivedUnit] = []
    for unit in remaining:
        expected_model = open_serials.get(unit.serial) if unit.serial else None
        if expected_model is not None and expected_model != unit.model_id:
            models[expected_model].serial_lines.remove(unit.serial)
            del open_serials[unit.serial]
            findings.append(
                Finding(
                    "model_mismatch",
                    unit.model_id,
                    expected_serial=unit.serial,
                    received_serial=unit.serial,
                    asset_id=unit.asset_id,
                )
            )
        else:
            leftover.append(unit)

    for unit in leftover:
        target = models[unit.model_id]
        (target.with_serial if unit.serial else target.without_serial).append(unit)

    for model_id in sorted(models):
        m = models[model_id]
        # 3. Units without serial stand for serial lines, then quantity lines
        while m.without_serial and m.serial_lines:
            m.without_serial.pop(0)
            m.serial_lines.pop(0)
        while m.without_serial and m.quantity:
            m.without_serial.pop(0)
            m.quantity -= 1
        # 4. Unexpected serials fill quantity lines, then pair with open serial lines
        while m.with_serial and m.quantity:
            m.with_serial.pop(0)
            m.quantity -= 1
        while m.with_serial and m.serial_lines:
            unit = m.with_serial.pop(0)
            findings.append(
                Finding(
                    "serial_mismatch",
                    model_id,
                    expected_serial=m.serial_lines.pop(0),
                    received_serial=unit.serial,
                    asset_id=unit.asset_id,
                )
            )
        # 5. Still expected / still received
        for serial in m.serial_lines:
            findings.append(Finding("shortage", model_id, expected_serial=serial))
        if m.quantity:
            findings.append(Finding("shortage", model_id, quantity=m.quantity))
        for unit in m.with_serial + m.without_serial:
            findings.append(
                Finding("surplus", model_id, received_serial=unit.serial, asset_id=unit.asset_id)
            )
    return findings
