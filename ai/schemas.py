from pydantic import BaseModel, Field, field_validator


class CriteriaScores(BaseModel):
    greeting: int = Field(ge=0, le=10)
    needs_discovery: int = Field(ge=0, le=10)
    politeness: int = Field(ge=0, le=10)
    speed_and_initiative: int = Field(ge=0, le=10)
    objections_handling: int = Field(ge=0, le=10)
    follow_up_pressure: int = Field(ge=0, le=10)
    close_to_action: int = Field(ge=0, le=10)
    emotional_contact: int = Field(ge=0, le=10)
    literacy: int = Field(ge=0, le=10)
    sales_structure: int = Field(ge=0, le=10)


class SalesQAResult(BaseModel):
    score: int = Field(ge=0, le=100)
    sale_probability: int = Field(ge=0, le=100)
    summary: str = Field(min_length=5)
    strengths: list[str] = Field(default_factory=list)
    mistakes: list[str] = Field(default_factory=list)
    missed_opportunities: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    criteria_scores: CriteriaScores

    @field_validator("strengths", "mistakes", "missed_opportunities", "recommendations")
    @classmethod
    def non_empty_items(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]
