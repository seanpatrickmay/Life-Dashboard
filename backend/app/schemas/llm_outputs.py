from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel


class LLMOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReadinessPillarOutput(LLMOutputModel):
    score: float
    insight: str


class OverallReadinessOutput(LLMOutputModel):
    score_100: float
    label: str
    insight: str


class ReadinessInsightOutput(LLMOutputModel):
    greeting: str
    hrv: ReadinessPillarOutput
    rhr: ReadinessPillarOutput
    sleep: ReadinessPillarOutput
    training_load: ReadinessPillarOutput
    overall_readiness: OverallReadinessOutput


class NutritionFoodMentionOutput(LLMOutputModel):
    name: str
    quantity: float | None = None
    unit: str | None = None


class NutritionFoodExtractionOutput(LLMOutputModel):
    foods: list[NutritionFoodMentionOutput] = Field(default_factory=list)
    summary: str | None = None


class NutrientProfileOutput(RootModel[dict[str, float | None]]):
    pass


class RecipeDefinitionOutput(LLMOutputModel):
    name: str
    servings: float
    default_unit: str


class RecipeIngredientOutput(LLMOutputModel):
    name: str
    quantity: float
    unit: str


class RecipeSuggestionOutput(LLMOutputModel):
    recipe: RecipeDefinitionOutput
    ingredients: list[RecipeIngredientOutput] = Field(default_factory=list)


class TodoExtractionItemOutput(LLMOutputModel):
    text: str
    deadline_utc: str | None = None
    deadline_inferred: bool = False


class TodoExtractionOutput(LLMOutputModel):
    items: list[TodoExtractionItemOutput] = Field(default_factory=list)
    summary: str | None = None


class TodoAccomplishmentOutput(LLMOutputModel):
    text: str


class ProjectAssignmentOutputItem(LLMOutputModel):
    todo_id: int
    project_name: str
    confidence: float
    reason: str | None = None


class ProjectAssignmentOutput(LLMOutputModel):
    assignments: list[ProjectAssignmentOutputItem] = Field(default_factory=list)


class TodoCalendarTitleOutput(LLMOutputModel):
    title: str
    details: str | None = None


class AssistantActionPlanItemOutput(LLMOutputModel):
    action_type: str
    params: dict[str, Any] = Field(default_factory=dict)


class AssistantActionPlanOutput(LLMOutputModel):
    actions: list[AssistantActionPlanItemOutput] = Field(default_factory=list)


class AssistantToolCallOutput(LLMOutputModel):
    tool_id: str
    args: dict[str, Any] = Field(default_factory=dict)


class AssistantRouterOutput(LLMOutputModel):
    reply_mode: Literal["respond_only", "respond_and_call_tools"] = "respond_only"
    narrative_intent: str = "Respond helpfully."
    tool_calls: list[AssistantToolCallOutput] = Field(default_factory=list)


class JournalSourceTextItemOutput(LLMOutputModel):
    source_id: str
    text: str


class JournalSourceTextItemsOutput(LLMOutputModel):
    items: list[JournalSourceTextItemOutput] = Field(default_factory=list)


class JournalDedupedItemOutput(LLMOutputModel):
    source_ids: list[str] = Field(default_factory=list)
    text: str


class JournalDedupedItemsOutput(LLMOutputModel):
    items: list[JournalDedupedItemOutput] = Field(default_factory=list)


class JournalGroupOutput(LLMOutputModel):
    title: str
    item_ids: list[str] = Field(default_factory=list)


class JournalGroupingOutput(LLMOutputModel):
    groups: list[JournalGroupOutput] = Field(default_factory=list)


class IMessageProjectInferenceOutput(LLMOutputModel):
    project_name: str | None = None
    confidence: float = 0.0
    source_message_ids: list[int] = Field(default_factory=list)
    reason: str


class IMessageCalendarCreateOutput(LLMOutputModel):
    summary: str
    start_time: str
    end_time: str
    is_all_day: bool = False
    source_message_ids: list[int] = Field(default_factory=list)
    reason: str


class IMessageCalendarExtractionOutput(LLMOutputModel):
    calendar_creates: list[IMessageCalendarCreateOutput] = Field(default_factory=list)


class IMessageTodoCreateOutput(LLMOutputModel):
    text: str
    deadline_utc: str | None = None
    deadline_is_date_only: bool = False
    source_message_ids: list[int] = Field(default_factory=list)
    reason: str


class IMessageTodoCompletionOutput(LLMOutputModel):
    source_message_ids: list[int] = Field(default_factory=list)
    match_text: str
    reason: str


class IMessageJournalEntryOutput(LLMOutputModel):
    source_message_ids: list[int] = Field(default_factory=list)
    text: str
    reason: str


class IMessageWorkspaceUpdateOutput(LLMOutputModel):
    page_title: str
    search_query: str
    summary: str
    source_message_ids: list[int] = Field(default_factory=list)
    reason: str


class IMessageActionExtractionOutput(LLMOutputModel):
    todo_creates: list[IMessageTodoCreateOutput] = Field(default_factory=list)
    todo_completions: list[IMessageTodoCompletionOutput] = Field(default_factory=list)
    journal_entries: list[IMessageJournalEntryOutput] = Field(default_factory=list)
    workspace_updates: list[IMessageWorkspaceUpdateOutput] = Field(default_factory=list)


class IMessageJudgeDecisionOutput(LLMOutputModel):
    approved: bool
    reason: str


class IMessageActionJudgeOutput(LLMOutputModel):
    project_inference: IMessageJudgeDecisionOutput
    todo_creates: list[IMessageJudgeDecisionOutput] = Field(default_factory=list)
    todo_completions: list[IMessageJudgeDecisionOutput] = Field(default_factory=list)
    calendar_creates: list[IMessageJudgeDecisionOutput] = Field(default_factory=list)
    journal_entries: list[IMessageJudgeDecisionOutput] = Field(default_factory=list)
    workspace_updates: list[IMessageJudgeDecisionOutput] = Field(default_factory=list)


class IMessageDedupDecisionOutput(LLMOutputModel):
    is_duplicate: bool
    matched_candidate_id: int | None = None
    matched_candidate_type: str | None = None
    reason: str


class IMessagePageSelectionOutput(LLMOutputModel):
    mode: Literal["update_existing", "create_new", "skip"]
    page_id: int | None = None
    title: str | None = None
    reason: str


class IMessagePageMergeOutput(LLMOutputModel):
    title: str
    body: str
    reason: str
