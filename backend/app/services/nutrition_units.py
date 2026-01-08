from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ML_PER_UNIT = {
    'cup': 240.0,
    'cups': 240.0,
    'c': 240.0,
    'tbsp': 15.0,
    'tablespoon': 15.0,
    'tablespoons': 15.0,
    'tbs': 15.0,
    'tsp': 5.0,
    'teaspoon': 5.0,
    'teaspoons': 5.0,
    't': 5.0,
    'oz': 29.5735,
    'ounce': 29.5735,
    'ounces': 29.5735,
    'fl oz': 29.5735,
    'pint': 473.176,
    'pints': 473.176,
    'quart': 946.353,
    'quarts': 946.353,
    'ml': 1.0,
    'milliliter': 1.0,
    'milliliters': 1.0,
    'l': 1000.0,
    'liter': 1000.0,
    'liters': 1000.0,
}

GRAMS_PER_UNIT = {
    'g': 1.0,
    'gram': 1.0,
    'grams': 1.0,
    'kg': 1000.0,
    'kilogram': 1000.0,
    'kilograms': 1000.0,
    'oz': 28.3495,
    'ounce': 28.3495,
    'ounces': 28.3495,
    'lb': 453.592,
    'lbs': 453.592,
    'pound': 453.592,
    'pounds': 453.592,
    '100g': 100.0,
}


@dataclass
class NormalizedQuantity:
    quantity: float
    unit: str
    input_quantity: float
    input_unit: str
    display: str
    converted: bool


class NutritionUnitNormalizer:
    """Converts household volume units to the target food unit when possible."""

    def normalize(self, quantity: float, unit: str | None, target_unit: str | None) -> NormalizedQuantity:
        input_unit = (unit or 'serving').strip()
        target = (target_unit or input_unit or 'serving').strip()
        cleaned_input = _clean_unit(input_unit)
        cleaned_target = _clean_unit(target)
        display = _format_display(quantity, input_unit)
        source_quantity = quantity if quantity and quantity > 0 else 1.0

        if cleaned_input in GRAMS_PER_UNIT and cleaned_target in GRAMS_PER_UNIT:
            grams = source_quantity * GRAMS_PER_UNIT[cleaned_input]
            target_quantity = grams / GRAMS_PER_UNIT[cleaned_target]
            return NormalizedQuantity(
                quantity=target_quantity,
                unit=target,
                input_quantity=quantity if quantity and quantity > 0 else source_quantity,
                input_unit=input_unit,
                display=display,
                converted=True,
            )

        if cleaned_input in ML_PER_UNIT and cleaned_target in ML_PER_UNIT:
            ml_amount = source_quantity * ML_PER_UNIT[cleaned_input]
            target_quantity = ml_amount / ML_PER_UNIT[cleaned_target]
            return NormalizedQuantity(
                quantity=target_quantity,
                unit=target,
                input_quantity=quantity if quantity and quantity > 0 else source_quantity,
                input_unit=input_unit,
                display=display,
                converted=True,
            )

        return NormalizedQuantity(
            quantity=source_quantity,
            unit=target if target else input_unit,
            input_quantity=quantity if quantity and quantity > 0 else source_quantity,
            input_unit=input_unit,
            display=display,
            converted=False,
        )


def _clean_unit(unit: str) -> str:
    return unit.lower().strip()


def _format_display(quantity: float, unit: str) -> str:
    if unit:
        return f"{quantity} {unit}".strip()
    return str(quantity)
