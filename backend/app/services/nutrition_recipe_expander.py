"""Shared utility for walking a recipe component tree and accumulating nutrients."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.db.models.nutrition import NUTRIENT_DEFINITIONS

if TYPE_CHECKING:
    from app.db.models.nutrition import NutritionRecipe


@dataclass
class ExpandedComponent:
    """A single leaf ingredient produced by expanding a recipe tree."""
    ingredient_id: int
    ingredient_name: str
    quantity: float
    unit: str
    default_unit: str


def expand_recipe_components(
    recipe: NutritionRecipe,
    servings: float = 1.0,
) -> list[ExpandedComponent]:
    """Walk the recipe tree and return flattened leaf-ingredient components.

    Each returned component has its quantity scaled by *servings* and by
    the per-serving ratio at every level of nesting.
    """
    results: list[ExpandedComponent] = []

    def _walk(target_recipe: NutritionRecipe, multiplier: float) -> None:
        for comp in target_recipe.components:
            per_serving = (
                comp.quantity / target_recipe.servings
                if target_recipe.servings
                else comp.quantity
            )
            effective_qty = multiplier * per_serving
            if comp.ingredient:
                results.append(
                    ExpandedComponent(
                        ingredient_id=comp.ingredient.id,
                        ingredient_name=comp.ingredient.name,
                        quantity=effective_qty,
                        unit=comp.unit,
                        default_unit=comp.ingredient.default_unit,
                    )
                )
            elif comp.child_recipe:
                _walk(comp.child_recipe, effective_qty)

    _walk(recipe, servings)
    return results


def derive_recipe_nutrients(recipe: NutritionRecipe) -> dict[str, float | None]:
    """Compute aggregate nutrient totals for a recipe by walking its tree.

    Returns a dict keyed by nutrient slug with rounded totals.  If the
    recipe has no components, every value is ``None``.
    """
    if not recipe.components:
        return {definition.slug: None for definition in NUTRIENT_DEFINITIONS}

    totals: dict[str, float] = {definition.slug: 0.0 for definition in NUTRIENT_DEFINITIONS}

    def _accumulate(target_recipe: NutritionRecipe, multiplier: float) -> None:
        for comp in target_recipe.components:
            per_serving = (
                comp.quantity / target_recipe.servings
                if target_recipe.servings
                else comp.quantity
            )
            effective_qty = multiplier * per_serving
            if comp.ingredient:
                profile = comp.ingredient.profile
                for definition in NUTRIENT_DEFINITIONS:
                    value = getattr(profile, definition.column_name)
                    if value is None:
                        continue
                    totals[definition.slug] += value * effective_qty
            elif comp.child_recipe:
                _accumulate(comp.child_recipe, effective_qty)

    _accumulate(recipe, 1.0)
    return {slug: round(value, 4) for slug, value in totals.items()}
