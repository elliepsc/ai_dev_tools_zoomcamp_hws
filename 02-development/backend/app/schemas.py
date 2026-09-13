from pydantic import BaseModel, ConfigDict, Field


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class TeamOut(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class MatchCreate(BaseModel):
    home_team_id: int
    away_team_id: int
    home_score: int = Field(ge=0)
    away_score: int = Field(ge=0)
    round: int = Field(default=1, ge=1)


class MatchOut(MatchCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class StandingRow(BaseModel):
    team_id: int
    team: str
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    goal_diff: int
    points: int
