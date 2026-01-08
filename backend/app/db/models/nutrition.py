from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import ClassVar, TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from app.utils.timezone import eastern_now

if TYPE_CHECKING:
    from .entities import User


def enum_values(enum_cls):
    return [member.value for member in enum_cls]


class NutrientCategory(str, Enum):
    MACRO = "macro"
    MICRO = "micro"


class NutrientGroup(str, Enum):
    MACRO = "macro"
    VITAMIN = "vitamin"
    MINERAL = "mineral"


@dataclass(frozen=True)
class NutrientDefinition:
    slug: str
    display_name: str
    category: NutrientCategory
    group: NutrientGroup
    unit: str
    column_name: str
    default_goal: float


NUTRIENT_DEFINITIONS: tuple[NutrientDefinition, ...] = (
    NutrientDefinition(
        "calories",
        "Calories",
        NutrientCategory.MACRO,
        NutrientGroup.MACRO,
        "kcal",
        "calories_kcal",
        2000,
    ),
    NutrientDefinition(
        "protein",
        "Protein",
        NutrientCategory.MACRO,
        NutrientGroup.MACRO,
        "g",
        "protein_g",
        120,
    ),
    NutrientDefinition(
        "carbohydrates",
        "Carbohydrates",
        NutrientCategory.MACRO,
        NutrientGroup.MACRO,
        "g",
        "carbohydrates_g",
        250,
    ),
    NutrientDefinition(
        "fat", "Fat", NutrientCategory.MACRO, NutrientGroup.MACRO, "g", "fat_g", 70
    ),
    NutrientDefinition(
        "fiber",
        "Fiber",
        NutrientCategory.MACRO,
        NutrientGroup.MACRO,
        "g",
        "fiber_g",
        30,
    ),
    NutrientDefinition(
        "vitamin_a",
        "Vitamin A",
        NutrientCategory.MICRO,
        NutrientGroup.VITAMIN,
        "µg RAE",
        "vitamin_a_ug",
        900,
    ),
    NutrientDefinition(
        "vitamin_c",
        "Vitamin C",
        NutrientCategory.MICRO,
        NutrientGroup.VITAMIN,
        "mg",
        "vitamin_c_mg",
        90,
    ),
    NutrientDefinition(
        "vitamin_d",
        "Vitamin D",
        NutrientCategory.MICRO,
        NutrientGroup.VITAMIN,
        "IU",
        "vitamin_d_iu",
        800,
    ),
    NutrientDefinition(
        "vitamin_e",
        "Vitamin E",
        NutrientCategory.MICRO,
        NutrientGroup.VITAMIN,
        "mg",
        "vitamin_e_mg",
        15,
    ),
    NutrientDefinition(
        "vitamin_k",
        "Vitamin K",
        NutrientCategory.MICRO,
        NutrientGroup.VITAMIN,
        "µg",
        "vitamin_k_ug",
        120,
    ),
    NutrientDefinition(
        "vitamin_b1",
        "Vitamin B1 (Thiamin)",
        NutrientCategory.MICRO,
        NutrientGroup.VITAMIN,
        "mg",
        "vitamin_b1_mg",
        1.2,
    ),
    NutrientDefinition(
        "vitamin_b2",
        "Vitamin B2 (Riboflavin)",
        NutrientCategory.MICRO,
        NutrientGroup.VITAMIN,
        "mg",
        "vitamin_b2_mg",
        1.3,
    ),
    NutrientDefinition(
        "vitamin_b3",
        "Vitamin B3 (Niacin)",
        NutrientCategory.MICRO,
        NutrientGroup.VITAMIN,
        "mg",
        "vitamin_b3_mg",
        16,
    ),
    NutrientDefinition(
        "vitamin_b6",
        "Vitamin B6",
        NutrientCategory.MICRO,
        NutrientGroup.VITAMIN,
        "mg",
        "vitamin_b6_mg",
        1.3,
    ),
    NutrientDefinition(
        "vitamin_b12",
        "Vitamin B12",
        NutrientCategory.MICRO,
        NutrientGroup.VITAMIN,
        "µg",
        "vitamin_b12_ug",
        2.4,
    ),
    NutrientDefinition(
        "folate",
        "Folate",
        NutrientCategory.MICRO,
        NutrientGroup.VITAMIN,
        "µg",
        "folate_ug",
        400,
    ),
    NutrientDefinition(
        "choline",
        "Choline",
        NutrientCategory.MICRO,
        NutrientGroup.VITAMIN,
        "mg",
        "choline_mg",
        550,
    ),
    NutrientDefinition(
        "calcium",
        "Calcium",
        NutrientCategory.MICRO,
        NutrientGroup.MINERAL,
        "mg",
        "calcium_mg",
        1000,
    ),
    NutrientDefinition(
        "iron",
        "Iron",
        NutrientCategory.MICRO,
        NutrientGroup.MINERAL,
        "mg",
        "iron_mg",
        18,
    ),
    NutrientDefinition(
        "magnesium",
        "Magnesium",
        NutrientCategory.MICRO,
        NutrientGroup.MINERAL,
        "mg",
        "magnesium_mg",
        420,
    ),
    NutrientDefinition(
        "potassium",
        "Potassium",
        NutrientCategory.MICRO,
        NutrientGroup.MINERAL,
        "mg",
        "potassium_mg",
        4700,
    ),
    NutrientDefinition(
        "sodium",
        "Sodium",
        NutrientCategory.MICRO,
        NutrientGroup.MINERAL,
        "mg",
        "sodium_mg",
        1500,
    ),
    NutrientDefinition(
        "zinc",
        "Zinc",
        NutrientCategory.MICRO,
        NutrientGroup.MINERAL,
        "mg",
        "zinc_mg",
        11,
    ),
    NutrientDefinition(
        "selenium",
        "Selenium",
        NutrientCategory.MICRO,
        NutrientGroup.MINERAL,
        "µg",
        "selenium_ug",
        55,
    ),
)

NUTRIENT_COLUMN_BY_SLUG: dict[str, str] = {
    definition.slug: definition.column_name for definition in NUTRIENT_DEFINITIONS
}
DEFAULT_GOAL_BY_SLUG: dict[str, float] = {
    definition.slug: definition.default_goal for definition in NUTRIENT_DEFINITIONS
}


def goal_column(slug: str) -> str:
    return f"goal_{slug}"


def multiplier_column(slug: str) -> str:
    return f"mult_{slug}"


class NutritionNutrient(Base):
    __tablename__ = "nutrition_nutrients"

    slug: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    category: Mapped[NutrientCategory] = mapped_column(
        SAEnum(
            NutrientCategory,
            name="nutrition_nutrient_category",
            values_callable=enum_values,
        )
    )
    group: Mapped[NutrientGroup] = mapped_column(
        SAEnum(
            NutrientGroup,
            name="nutrition_nutrient_group",
            values_callable=enum_values,
        )
    )
    unit: Mapped[str] = mapped_column(String(32))
    default_goal: Mapped[float]


class NutritionIngredientProfile(Base):
    __tablename__ = "nutrition_food_profiles"

    _column_map: ClassVar[dict[str, str]] = {
        definition.slug: definition.column_name for definition in NUTRIENT_DEFINITIONS
    }

    # dynamically define a float column for each nutrient definition
    for definition in NUTRIENT_DEFINITIONS:
        locals()[definition.column_name] = mapped_column(Float, nullable=True)

    ingredients: Mapped[list["NutritionIngredient"]] = relationship(back_populates="profile")


class NutritionIngredientStatus(str, Enum):
    CONFIRMED = "confirmed"
    UNCONFIRMED = "unconfirmed"


class NutritionIngredient(Base):
    __tablename__ = "nutrition_foods"

    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    default_unit: Mapped[str] = mapped_column(String(64), default="serving")
    status: Mapped[NutritionIngredientStatus] = mapped_column(
        SAEnum(
            NutritionIngredientStatus,
            name="nutrition_food_status",
            values_callable=enum_values,
        ),
        default=NutritionIngredientStatus.UNCONFIRMED,
    )
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, default=1)
    profile_id: Mapped[int] = mapped_column(ForeignKey("nutrition_food_profiles.id"))

    profile: Mapped[NutritionIngredientProfile] = relationship(back_populates="ingredients")
    intakes: Mapped[list["NutritionIntake"]] = relationship(back_populates="ingredient")


class NutritionRecipe(Base):
    __tablename__ = "nutrition_recipes"

    name: Mapped[str] = mapped_column(String(255), index=True)
    default_unit: Mapped[str] = mapped_column(String(64), default="serving")
    servings: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[NutritionIngredientStatus] = mapped_column(
        SAEnum(
            NutritionIngredientStatus,
            name="nutrition_recipe_status",
            values_callable=enum_values,
        ),
        default=NutritionIngredientStatus.UNCONFIRMED,
    )
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, default=1)

    components: Mapped[list["NutritionRecipeComponent"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan", foreign_keys="NutritionRecipeComponent.recipe_id"
    )


class NutritionRecipeComponent(Base):
    __tablename__ = "nutrition_recipe_components"

    recipe_id: Mapped[int] = mapped_column(ForeignKey("nutrition_recipes.id"), nullable=False)
    ingredient_id: Mapped[int | None] = mapped_column(ForeignKey("nutrition_foods.id"), nullable=True)
    child_recipe_id: Mapped[int | None] = mapped_column(ForeignKey("nutrition_recipes.id"), nullable=True)
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(64))
    position: Mapped[int | None] = mapped_column(nullable=True)

    recipe: Mapped[NutritionRecipe] = relationship(
        back_populates="components",
        foreign_keys=[recipe_id],
    )
    ingredient: Mapped[NutritionIngredient | None] = relationship(
        foreign_keys=[ingredient_id]
    )
    child_recipe: Mapped[NutritionRecipe | None] = relationship(
        "NutritionRecipe",
        foreign_keys=[child_recipe_id],
        post_update=True,
        viewonly=True,
    )


class NutritionIntakeSource(str, Enum):
    MANUAL = "manual"
    CLAUDE = "claude"


class NutritionIntake(Base):
    __tablename__ = "nutrition_intake"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    ingredient_id: Mapped[int] = mapped_column("food_id", ForeignKey("nutrition_foods.id"))
    quantity: Mapped[float]
    unit: Mapped[str] = mapped_column(String(64))
    day_date: Mapped[date] = mapped_column(Date)
    source: Mapped[NutritionIntakeSource] = mapped_column(
        SAEnum(
            NutritionIntakeSource,
            name="nutrition_intake_source",
            values_callable=enum_values,
        )
    )
    claude_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    ingredient: Mapped[NutritionIngredient] = relationship(back_populates="intakes")
    user: Mapped["User"] = relationship(back_populates="nutrition_intakes")


class ScalingRuleType(str, Enum):
    CATALOG = "catalog"
    MANUAL = "manual"


class NutrientScalingRule(Base):
    __tablename__ = "nutrient_scaling_rule"
    __table_args__ = (UniqueConstraint("owner_user_id", name="uq_scaling_rule_owner"),)

    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(255))
    type: Mapped[ScalingRuleType] = mapped_column(
        SAEnum(
            ScalingRuleType,
            name="nutrient_scaling_rule_type",
            values_callable=enum_values,
            create_type=False,
        ),
        default=ScalingRuleType.CATALOG,
    )
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), nullable=True)

    for definition in NUTRIENT_DEFINITIONS:
        locals()[multiplier_column(definition.slug)] = mapped_column(Float, default=1.0)

    owner: Mapped["User"] = relationship(lazy="joined")
    assignments: Mapped[list["UserNutrientScalingRule"]] = relationship(back_populates="rule")


class UserNutrientScalingRule(Base):
    __tablename__ = "user_nutrient_scaling_rule"
    __table_args__ = (UniqueConstraint("user_id", "rule_id", name="uq_user_rule"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    rule_id: Mapped[int] = mapped_column(ForeignKey("nutrient_scaling_rule.id"), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=eastern_now)

    user: Mapped["User"] = relationship(back_populates="scaling_rules")
    rule: Mapped[NutrientScalingRule] = relationship(back_populates="assignments")


class NutritionGoal(Base):
    __tablename__ = "nutrition_goal"
    __table_args__ = (UniqueConstraint("user_id", name="uq_nutrition_goal_user_id"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    computed_from_date: Mapped[date | None]
    computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    calorie_source: Mapped[str | None] = mapped_column(String(64))

    for definition in NUTRIENT_DEFINITIONS:
        locals()[goal_column(definition.slug)] = mapped_column(Float, nullable=True)

    user: Mapped["User"] = relationship(lazy="joined")
