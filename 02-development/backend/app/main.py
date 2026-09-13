"""FastAPI application for the sports-league scoreboard.

Endpoints (see the generated OpenAPI at /docs or openapi.yaml):
  GET  /api/health
  GET  /api/teams          POST /api/teams
  GET  /api/matches        POST /api/matches
  GET  /api/standings      (computed league table)
"""
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models, schemas
from .db import Base, engine, get_db
from .standings import compute_standings


def create_app() -> FastAPI:
    Base.metadata.create_all(bind=engine)

    app = FastAPI(title="TopTable — League Scoreboard API", version="1.0.0")

    # Dev CORS: allow the Vite dev server (and any origin) to call the API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/teams", response_model=list[schemas.TeamOut])
    def list_teams(db: Session = Depends(get_db)):
        return db.scalars(select(models.Team).order_by(models.Team.name)).all()

    @app.post("/api/teams", response_model=schemas.TeamOut, status_code=201)
    def create_team(payload: schemas.TeamCreate, db: Session = Depends(get_db)):
        exists = db.scalar(select(models.Team).where(models.Team.name == payload.name))
        if exists:
            raise HTTPException(status_code=409, detail="team already exists")
        team = models.Team(name=payload.name)
        db.add(team)
        db.commit()
        db.refresh(team)
        return team

    @app.get("/api/matches", response_model=list[schemas.MatchOut])
    def list_matches(db: Session = Depends(get_db)):
        return db.scalars(select(models.Match).order_by(models.Match.id)).all()

    @app.post("/api/matches", response_model=schemas.MatchOut, status_code=201)
    def create_match(payload: schemas.MatchCreate, db: Session = Depends(get_db)):
        if payload.home_team_id == payload.away_team_id:
            raise HTTPException(status_code=400, detail="a team cannot play itself")
        for tid in (payload.home_team_id, payload.away_team_id):
            if db.get(models.Team, tid) is None:
                raise HTTPException(status_code=404, detail=f"team {tid} not found")
        match = models.Match(**payload.model_dump())
        db.add(match)
        db.commit()
        db.refresh(match)
        return match

    @app.get("/api/standings", response_model=list[schemas.StandingRow])
    def standings(db: Session = Depends(get_db)):
        teams = db.scalars(select(models.Team)).all()
        matches = db.scalars(select(models.Match)).all()
        return compute_standings(teams, matches)

    return app


app = create_app()
