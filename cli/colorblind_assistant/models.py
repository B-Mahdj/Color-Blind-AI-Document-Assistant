"""The bounded interface between the vision model and the PDF editor."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Action(StrictModel):
    kind: Literal["recolor", "hatch", "dash", "label"]
    target_ids: list[str] = Field(min_length=1, max_length=100)
    channel: Literal["fill", "stroke"] | None = None
    color: str | None = None
    style: Literal["diagonal", "cross", "dashed", "dotted", "dashdot", "longdash"] | None = None
    source_text_id: str | None = None


class CorrectionGroup(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=1000)
    evidence_text_ids: list[str] = Field(max_length=100)
    association: Literal["legend", "direct_labels", "ordered_scale", "image_palette", "image_ordered"]
    palette_order: list[str] = Field(default_factory=list, max_length=100)
    legend_ids: list[str] = Field(max_length=100)
    uncertain: bool
    actions: list[Action] = Field(min_length=1, max_length=100)


class PagePlan(StrictModel):
    groups: list[CorrectionGroup] = Field(max_length=30)
    warnings: list[str] = Field(max_length=30)


class PageReview(StrictModel):
    approved: bool
    revised_plan: PagePlan | None
    warnings: list[str] = Field(max_length=30)
