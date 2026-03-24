from __future__ import annotations

from collections import deque
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.db.models.nutrition import (
    NUTRIENT_DEFINITIONS,
    NutritionIngredientStatus,
    NutritionRecipe,
    NutritionRecipeComponent,
)
from app.db.repositories.nutrition_ingredients_repository import (
    NutritionIngredientsRepository,
    NutritionRecipesRepository,
)
from app.services.nutrition_recipe_expander import derive_recipe_nutrients


class NutritionRecipesService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.recipes_repo = NutritionRecipesRepository(session)
        self.ingredients_repo = NutritionIngredientsRepository(session)

    async def list_recipes(self, owner_user_id: int) -> list[dict[str, Any]]:
        recipes = await self.recipes_repo.list_recipes(owner_user_id)
        return [self._serialize_recipe(recipe, include_components=False) for recipe in recipes]

    async def get_recipe(self, recipe_id: int, *, owner_user_id: int) -> dict[str, Any]:
        recipe = await self.recipes_repo.get_recipe(recipe_id, owner_user_id, load_components=True)
        if recipe is None:
            raise NotFoundException("Recipe not found")
        return self._serialize_recipe(recipe, include_components=True)

    async def create_recipe(
        self,
        *,
        name: str,
        default_unit: str,
        servings: float,
        status: NutritionIngredientStatus,
        owner_user_id: int,
        components: list[dict[str, Any]],
        source: str | None = None,
    ) -> dict[str, Any]:
        await self._assert_no_cycles(None, components, owner_user_id=owner_user_id)
        recipe = await self.recipes_repo.create_recipe(
            name=name,
            default_unit=default_unit,
            servings=servings,
            status=status,
            owner_user_id=owner_user_id,
            components=components,
            source=source,
        )
        await self.session.commit()
        recipe = await self.recipes_repo.get_recipe(recipe.id, owner_user_id, load_components=True)
        return self._serialize_recipe(recipe, include_components=True)  # type: ignore[arg-type]

    async def update_recipe(
        self,
        recipe_id: int,
        *,
        owner_user_id: int,
        name: str | None = None,
        default_unit: str | None = None,
        servings: float | None = None,
        status: NutritionIngredientStatus | None = None,
        components: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        recipe = await self.recipes_repo.get_recipe(recipe_id, owner_user_id, load_components=True)
        if recipe is None:
            raise NotFoundException("Recipe not found")
        if components is not None:
            await self._assert_no_cycles(recipe_id, components, owner_user_id=owner_user_id)
        await self.recipes_repo.update_recipe(
            recipe,
            name=name,
            default_unit=default_unit,
            servings=servings,
            status=status,
            components=components,
        )
        await self.session.commit()
        recipe = await self.recipes_repo.get_recipe(recipe_id, owner_user_id, load_components=True)
        return self._serialize_recipe(recipe, include_components=True)  # type: ignore[arg-type]

    async def _assert_no_cycles(
        self, recipe_id: int | None, components: list[dict[str, Any]], *, owner_user_id: int
    ) -> None:
        """Prevent recipe -> child_recipe cycles by checking new edges."""
        edges: dict[int, set[int]] = {}
        recipes = await self.recipes_repo.list_recipes(owner_user_id=owner_user_id, load_components=True)
        for recipe in recipes:
            if recipe.id not in edges:
                edges[recipe.id] = set()
            for comp in recipe.components:
                if comp.child_recipe_id:
                    edges[recipe.id].add(comp.child_recipe_id)
        if recipe_id is not None:
            edges[recipe_id] = set()
        temp_id = recipe_id or -1
        edges.setdefault(temp_id, set())
        for comp in components:
            child_id = comp.get("child_recipe_id")
            if child_id:
                edges[temp_id].add(child_id)

        def has_path(start: int, target: int) -> bool:
            visited: set[int] = set()
            queue: deque[int] = deque([start])
            while queue:
                current = queue.popleft()
                if current == target:
                    return True
                for neighbor in edges.get(current, set()):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            return False

        if recipe_id is None:
            current_id = -1
        else:
            current_id = recipe_id

        for comp in components:
            child_id = comp.get("child_recipe_id")
            if child_id and has_path(child_id, current_id):
                raise ValueError("Recipes cannot reference each other in a cycle.")

    def _serialize_recipe(self, recipe: NutritionRecipe, include_components: bool) -> dict[str, Any]:
        components = []
        if include_components:
            for comp in sorted(recipe.components, key=lambda c: c.position or 0):
                components.append(
                    {
                        "ingredient_id": comp.ingredient_id,
                        "child_recipe_id": comp.child_recipe_id,
                        "ingredient_name": comp.ingredient.name if comp.ingredient else None,
                        "child_recipe_name": comp.child_recipe.name if comp.child_recipe else None,
                        "quantity": comp.quantity,
                        "unit": comp.unit,
                        "position": comp.position,
                    }
                )
        derived = derive_recipe_nutrients(recipe) if include_components else {}
        return {
            "id": recipe.id,
            "owner_user_id": recipe.owner_user_id,
            "name": recipe.name,
            "default_unit": recipe.default_unit,
            "servings": recipe.servings,
            "status": recipe.status.value,
            "components": components,
            "derived_nutrients": derived,
        }
