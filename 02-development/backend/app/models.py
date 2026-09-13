from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("home_team_id", "away_team_id", "round", name="uq_match"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    home_score: Mapped[int] = mapped_column(Integer)
    away_score: Mapped[int] = mapped_column(Integer)
    round: Mapped[int] = mapped_column(Integer, default=1)

    home_team = relationship("Team", foreign_keys=[home_team_id])
    away_team = relationship("Team", foreign_keys=[away_team_id])
