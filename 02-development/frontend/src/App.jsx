import React, { useEffect, useState } from "react";
import { api } from "./api.js";

export default function App() {
  const [teams, setTeams] = useState([]);
  const [matches, setMatches] = useState([]);
  const [standings, setStandings] = useState([]);
  const [error, setError] = useState("");

  const [teamName, setTeamName] = useState("");
  const [form, setForm] = useState({ home: "", away: "", hs: "", as: "" });

  const refresh = async () => {
    try {
      const [t, m, s] = await Promise.all([
        api.listTeams(),
        api.listMatches(),
        api.standings(),
      ]);
      setTeams(t);
      setMatches(m);
      setStandings(s);
      setError("");
    } catch (e) {
      setError(`Cannot reach the backend at ${api.baseUrl} — is it running? (${e.message})`);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const addTeam = async (e) => {
    e.preventDefault();
    if (!teamName.trim()) return;
    try {
      await api.addTeam(teamName.trim());
      setTeamName("");
      refresh();
    } catch (e) {
      setError(e.message);
    }
  };

  const addMatch = async (e) => {
    e.preventDefault();
    try {
      await api.addMatch({
        home_team_id: Number(form.home),
        away_team_id: Number(form.away),
        home_score: Number(form.hs),
        away_score: Number(form.as),
      });
      setForm({ home: "", away: "", hs: "", as: "" });
      refresh();
    } catch (e) {
      setError(e.message);
    }
  };

  const teamName_ = (id) => teams.find((t) => t.id === id)?.name || `#${id}`;

  return (
    <div className="wrap">
      <header>
        <h1>🏆 TopTable</h1>
        <span className="api">API: {api.baseUrl}</span>
      </header>

      {error && <div className="error">{error}</div>}

      <section className="panel">
        <h2>Standings</h2>
        {standings.length === 0 ? (
          <p className="muted">No teams yet. Add teams and record matches below.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>#</th><th>Team</th><th>P</th><th>W</th><th>D</th><th>L</th>
                <th>GF</th><th>GA</th><th>GD</th><th>Pts</th>
              </tr>
            </thead>
            <tbody>
              {standings.map((r, i) => (
                <tr key={r.team_id}>
                  <td>{i + 1}</td>
                  <td className="team">{r.team}</td>
                  <td>{r.played}</td><td>{r.won}</td><td>{r.drawn}</td><td>{r.lost}</td>
                  <td>{r.goals_for}</td><td>{r.goals_against}</td><td>{r.goal_diff}</td>
                  <td className="pts">{r.points}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <div className="two-col">
        <section className="panel">
          <h2>Add a team</h2>
          <form onSubmit={addTeam} className="row">
            <input
              value={teamName}
              onChange={(e) => setTeamName(e.target.value)}
              placeholder="Team name"
            />
            <button type="submit">Add</button>
          </form>
        </section>

        <section className="panel">
          <h2>Record a match</h2>
          <form onSubmit={addMatch} className="match-form">
            <select value={form.home} onChange={(e) => setForm({ ...form, home: e.target.value })} required>
              <option value="">Home team</option>
              {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
            <input type="number" min="0" value={form.hs} onChange={(e) => setForm({ ...form, hs: e.target.value })} placeholder="0" required />
            <span>–</span>
            <input type="number" min="0" value={form.as} onChange={(e) => setForm({ ...form, as: e.target.value })} placeholder="0" required />
            <select value={form.away} onChange={(e) => setForm({ ...form, away: e.target.value })} required>
              <option value="">Away team</option>
              {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
            <button type="submit">Save</button>
          </form>
        </section>
      </div>

      <section className="panel">
        <h2>Matches</h2>
        {matches.length === 0 ? (
          <p className="muted">No matches recorded yet.</p>
        ) : (
          <ul className="matches">
            {matches.map((m) => (
              <li key={m.id}>
                {teamName_(m.home_team_id)} <strong>{m.home_score} – {m.away_score}</strong> {teamName_(m.away_team_id)}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
