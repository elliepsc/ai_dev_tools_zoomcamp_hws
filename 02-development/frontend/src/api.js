// All backend calls are centralized here (as the homework asks). The backend
// base URL is configurable via VITE_API_URL and defaults to the local FastAPI.
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(method, path, body) {
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* keep statusText */
    }
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  baseUrl: API_URL,
  health: () => request("GET", "/api/health"),
  listTeams: () => request("GET", "/api/teams"),
  addTeam: (name) => request("POST", "/api/teams", { name }),
  listMatches: () => request("GET", "/api/matches"),
  addMatch: (match) => request("POST", "/api/matches", match),
  standings: () => request("GET", "/api/standings"),
};
