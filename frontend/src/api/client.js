// src/api/client.js
//
// WHY THIS FILE EXISTS:
// Instead of writing "http://localhost:5000" in every component,
// we create ONE Axios instance here with the base URL set.
// Every API call in the app imports from this file.
// If the Flask URL ever changes (e.g. deployed to production),
// you change it in ONE place, not across 10 components.
//
// axios.create() returns a new Axios instance with custom defaults.
// baseURL: all requests using this instance will prepend this URL.
// So apiClient.get('/api/matches') calls http://localhost:5000/api/matches
//
// NAMED EXPORTS vs DEFAULT EXPORT:
//   The default export (apiClient) is the raw Axios instance.
//   Named exports are purpose-built functions that wrap specific endpoints.
//   Components that need a specific endpoint import the named function.
//   Components that make varied or dynamic requests import apiClient directly.
//   This keeps API knowledge in one file — not scattered across components.

import axios from 'axios'

const apiClient = axios.create({
  baseURL: 'http://localhost:5000',
  // timeout: how long to wait before giving up on a request (ms)
  // 30 seconds — pipeline can take ~22s per the continuation doc
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

/**
 * getMatchStats(matchId)
 *
 * Fetches aggregated team-level stats for a match.
 * Calls GET /api/matches/<id>/stats
 *
 * Returns the response data directly (not the full Axios response object).
 * Shape when available:
 *   {
 *     match_id: 551957,
 *     available: true,
 *     home: { team: "FC Barcelona", xg: 3.18, shots: 18, ... },
 *     away: { team: "FC København", xg: 1.06, shots: 7, ... }
 *   }
 *
 * Shape when no stats in DB:
 *   { match_id: 551957, available: false, note: "..." }
 *
 * WHY .then(res => res.data):
 *   Axios wraps responses in { data, status, headers, ... }.
 *   Callers of this function don't care about HTTP metadata —
 *   they just want the parsed JSON body. Unwrapping here keeps
 *   components clean.
 */
export function getMatchStats(matchId) {
  return apiClient
    .get(`/api/matches/${matchId}/stats`)
    .then(res => res.data)
}

export default apiClient
