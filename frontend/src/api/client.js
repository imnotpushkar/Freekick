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

import axios from 'axios'

const apiClient = axios.create({
  baseURL: 'http://localhost:5000',
  // timeout: how long to wait before giving up on a request (ms)
  timeout: 30000, // 30 seconds — pipeline can take ~22s per the continuation doc
  headers: {
    'Content-Type': 'application/json',
  },
})

export default apiClient
