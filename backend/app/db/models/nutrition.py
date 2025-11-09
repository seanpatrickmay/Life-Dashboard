from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import ClassVar, TYPE_CHECKING

from sqlalchemy import Enum as SAEnum, Float, ForeignKey, String, UniqueConstraint, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

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

    goals: Mapped[list["NutritionUserGoal"]] = relationship(back_populates="nutrient")


class NutritionFoodProfile(Base):
    __tablename__ = "nutrition_food_profiles"

    _column_map: ClassVar[dict[str, str]] = {
        definition.slug: definition.column_name for definition in NUTRIENT_DEFINITIONS
    }

    # dynamically define a float column for each nutrient definition
    for definition in NUTRIENT_DEFINITIONS:
        locals()[definition.column_name] = mapped_column(Float, nullable=True)

    foods: Mapped[list["NutritionFood"]] = relationship(back_populates="profile")


class NutritionFoodStatus(str, Enum):
    CONFIRMED = "confirmed"
    UNCONFIRMED = "unconfirmed"


class NutritionFood(Base):
    __tablename__ = "nutrition_foods"

    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    default_unit: Mapped[str] = mapped_column(String(64), default="serving")
    status: Mapped[NutritionFoodStatus] = mapped_column(
        SAEnum(
            NutritionFoodStatus,
            name="nutrition_food_status",
            values_callable=enum_values,
        ),
        default=NutritionFoodStatus.UNCONFIRMED,
    )
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("nutrition_food_profiles.id"))

    profile: Mapped[NutritionFoodProfile] = relationship(back_populates="foods")
    intakes: Mapped[list["NutritionIntake"]] = relationship(back_populates="food")


class NutritionUserGoal(Base):
    __tablename__ = "nutrition_user_goals"
    __table_args__ = (
        UniqueConstraint("user_id", "nutrient_id", name="uq_user_nutrient_goal"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    nutrient_id: Mapped[int] = mapped_column(ForeignKey("nutrition_nutrients.id"))
    daily_goal: Mapped[float]

    nutrient: Mapped[NutritionNutrient] = relationship(back_populates="goals")
    user: Mapped["User"] = relationship(back_populates="nutrition_goals")


class NutritionIntakeSource(str, Enum):
    MANUAL = "manual"
    CLAUDE = "claude"


class NutritionIntake(Base):
    __tablename__ = "nutrition_intake"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    food_id: Mapped[int] = mapped_column(ForeignKey("nutrition_foods.id"))
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

    food: Mapped[NutritionFood] = relationship(back_populates="intakes")
    user: Mapped["User"] = relationship(back_populates="nutrition_intakes")
