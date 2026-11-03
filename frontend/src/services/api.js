
// Centralized API client for QuizVoro

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const WS_BASE_URL =
  import.meta.env.VITE_WS_BASE_URL ||
  API_BASE_URL.replace(/^http:\/\//, "ws://").replace(/^https:\/\//, "wss://");

const TOKEN_KEY = "quizvoro_admin_token";
const USERNAME_KEY = "quizvoro_admin_username";
const PARTICIPANT_TOKEN_KEY = "quizvoro_participant_token";
const PARTICIPANT_INFO_KEY = "quizvoro_participant_info";

// ── Auth helpers ─────────────────────────────────────────────────────────────

export function getAdminToken() {
  return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY) || null;
}

export function setAdminToken(token, username = "", persist = true) {
  const storage = persist ? localStorage : sessionStorage;
  storage.setItem(TOKEN_KEY, token);
  if (username) {
    storage.setItem(USERNAME_KEY, username);
  }
}

export function clearAdminToken() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USERNAME_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USERNAME_KEY);
}

export function getAdminUsername() {
  return (
    localStorage.getItem(USERNAME_KEY) ||
    sessionStorage.getItem(USERNAME_KEY) ||
    "admin"
  );
}

export function isAdminAuthenticated() {
  return Boolean(getAdminToken());
}

// ── Participant token helpers ────────────────────────────────────────────────
// Each browser tab gets its own participant session.
// This allows multiple players to use the same Chrome browser.

export function getParticipantToken() {
  return sessionStorage.getItem(PARTICIPANT_TOKEN_KEY) || null;
}

export function setParticipantSession(sessionData) {
  if (sessionData?.token) {
    sessionStorage.setItem(PARTICIPANT_TOKEN_KEY, sessionData.token);
  }

  if (sessionData) {
    sessionStorage.setItem(
      PARTICIPANT_INFO_KEY,
      JSON.stringify(sessionData)
    );
  }
}

export function getParticipantSession() {
  try {
    const raw = sessionStorage.getItem(PARTICIPANT_INFO_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function clearParticipantSession() {
  sessionStorage.removeItem(PARTICIPANT_TOKEN_KEY);
  sessionStorage.removeItem(PARTICIPANT_INFO_KEY);

  // Remove old shared participant credentials.
  localStorage.removeItem(PARTICIPANT_TOKEN_KEY);
  localStorage.removeItem(PARTICIPANT_INFO_KEY);
}

// ── Centralized HTTP Request ─────────────────────────────────────────────────

export async function apiRequest(path, options = {}) {
  const headers = {
    ...options.headers,
  };

  // Only set application/json if body is not FormData
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  // Inject Admin JWT if available and not specifically excluded
  if (!options.skipAuth) {
    const adminToken = getAdminToken();
    if (adminToken && !headers["Authorization"]) {
      headers["Authorization"] = `Bearer ${adminToken}`;
    }
  }

  // Inject Participant token if present and not set
  if (options.useParticipantToken) {
    const pToken = getParticipantToken();
    if (pToken && !headers["X-Participant-Token"]) {
      headers["X-Participant-Token"] = pToken;
    }
  }

  const url = path.startsWith("http") ? path : `${API_BASE_URL}${path}`;

  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (netErr) {
    throw new Error(
      `Network connection failed. Please ensure the backend is running at ${API_BASE_URL}. (${netErr.message})`
    );
  }

  if (response.status === 204) {
    return null;
  }

  let data;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    data = await response.json();
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    const errorMessage =
      (typeof data === "object" && data?.detail) ||
      (typeof data === "string" && data) ||
      `Request failed with status ${response.status}`;

    const error = new Error(errorMessage);
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
}

// ── Admin Authentication API ─────────────────────────────────────────────────

export const authApi = {
  async login(username, password) {
    const data = await apiRequest("/api/v1/admin/login", {
      method: "POST",
      skipAuth: true,
      body: JSON.stringify({ username, password }),
    });

    setAdminToken(data.access_token, username, true);
    return data;
  },

  async getMe() {
    return apiRequest("/api/v1/admin/me");
  },

  logout() {
    clearAdminToken();
  },
};

// ── Quizzes, Rounds, Questions API ───────────────────────────────────────────

export const quizApi = {
  // Quizzes
  async listQuizzes() {
    return apiRequest("/api/v1/quizzes");
  },

  async getQuiz(quizId) {
    return apiRequest(`/api/v1/quizzes/${quizId}`);
  },

  async createQuiz({ title, description = null }) {
    return apiRequest("/api/v1/quizzes", {
      method: "POST",
      body: JSON.stringify({ title, description }),
    });
  },

  async updateQuiz(quizId, { title, description, is_published }) {
    return apiRequest(`/api/v1/quizzes/${quizId}`, {
      method: "PATCH",
      body: JSON.stringify({ title, description, is_published }),
    });
  },

  async deleteQuiz(quizId) {
    return apiRequest(`/api/v1/quizzes/${quizId}`, {
      method: "DELETE",
    });
  },

  // Rounds
  async listRounds(quizId) {
    return apiRequest(`/api/v1/quizzes/${quizId}/rounds`);
  },

  async createRound(quizId, { title, description = null, round_number }) {
    return apiRequest(`/api/v1/quizzes/${quizId}/rounds`, {
      method: "POST",
      body: JSON.stringify({ title, description, round_number }),
    });
  },

  async getRound(roundId) {
    return apiRequest(`/api/v1/rounds/${roundId}`);
  },

  async updateRound(roundId, data) {
    return apiRequest(`/api/v1/rounds/${roundId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  async deleteRound(roundId) {
    return apiRequest(`/api/v1/rounds/${roundId}`, {
      method: "DELETE",
    });
  },

  // Questions
  async listQuestions(roundId) {
    return apiRequest(`/api/v1/rounds/${roundId}/questions`);
  },

  async createQuestion(roundId, questionData) {
    // questionData: { question_text, question_type: 'MCQ', time_limit, points, question_order, options: [{ option_text, is_correct }] }
    return apiRequest(`/api/v1/rounds/${roundId}/questions`, {
      method: "POST",
      body: JSON.stringify(questionData),
    });
  },

  async getQuestion(questionId) {
    return apiRequest(`/api/v1/questions/${questionId}`);
  },

  async updateQuestion(questionId, data) {
    return apiRequest(`/api/v1/questions/${questionId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  async deleteQuestion(questionId) {
    return apiRequest(`/api/v1/questions/${questionId}`, {
      method: "DELETE",
    });
  },

  // Media
  async uploadMedia(questionId, file) {
    const formData = new FormData();
    formData.append("file", file);

    return apiRequest(`/api/v1/questions/${questionId}/media`, {
      method: "POST",
      body: formData,
    });
  },
};

// ── Game Management & Host Controls ──────────────────────────────────────────

export const hostApi = {
  async createGame(quizId) {
    return apiRequest("/api/v1/games", {
      method: "POST",
      body: JSON.stringify({ quiz_id: Number(quizId) }),
    });
  },

  async getStageToken(gameId) {
    return apiRequest(`/api/v1/games/${gameId}/stage-token`);
  },

  async getGameState(gameId) {
    return apiRequest(`/api/v1/games/${gameId}/state`);
  },

  async startGame(gameId) {
    return apiRequest(`/api/v1/games/${gameId}/start`, {
      method: "POST",
    });
  },

  async nextQuestion(gameId) {
    return apiRequest(`/api/v1/games/${gameId}/next-question`, {
      method: "POST",
    });
  },

  async pauseGame(gameId) {
    return apiRequest(`/api/v1/games/${gameId}/pause`, {
      method: "POST",
    });
  },

  async resumeGame(gameId) {
    return apiRequest(`/api/v1/games/${gameId}/resume`, {
      method: "POST",
    });
  },

  async revealAnswer(gameId) {
    return apiRequest(`/api/v1/games/${gameId}/reveal`, {
      method: "POST",
    });
  },

  async scoreQuestion(gameId, questionId) {
    return apiRequest(`/api/v1/games/${gameId}/questions/${questionId}/score`, {
      method: "POST",
    });
  },

  async endGame(gameId) {
    return apiRequest(`/api/v1/games/${gameId}/end`, {
      method: "POST",
    });
  },

  async kickParticipant(gameId, participantId) {
    return apiRequest(`/api/v1/games/${gameId}/kick`, {
      method: "POST",
      body: JSON.stringify({ participant_id: Number(participantId) }),
    });
  },
};

export const stageApi = {
  async getGameState(gameId, token) {
    return apiRequest(
      `/api/v1/games/${gameId}/stage-state?token=${encodeURIComponent(token)}`,
      { skipAuth: true }
    );
  },

  async refreshToken(gameId, token) {
    return apiRequest(
      `/api/v1/games/${gameId}/stage-token/refresh?token=${encodeURIComponent(token)}`,
      { method: "POST", skipAuth: true }
    );
  },
};

// ── Participant API ──────────────────────────────────────────────────────────

export const participantApi = {
  async joinGame(pin, nickname) {
    const data = await apiRequest("/api/v1/games/join", {
      method: "POST",
      skipAuth: true,
      body: JSON.stringify({ pin, nickname }),
    });

    setParticipantSession(data);
    return data;
  },

  async rejoinGame(pin, token) {
    const data = await apiRequest("/api/v1/games/rejoin", {
      method: "POST",
      skipAuth: true,
      body: JSON.stringify({ pin, token }),
    });

    setParticipantSession(data);
    return data;
  },

  async getCurrentQuestion(gameId) {
    return apiRequest(`/api/v1/games/${gameId}/current-question`, {
      useParticipantToken: true,
    });
  },

  async submitAnswer(gameId, { question_id, option_id = null, selected_option = null }) {
    return apiRequest(`/api/v1/games/${gameId}/answers`, {
      method: "POST",
      useParticipantToken: true,
      body: JSON.stringify({ question_id, option_id, selected_option }),
    });
  },

  async getMyStats(gameId) {
    return apiRequest(`/api/v1/games/${gameId}/me`, {
      useParticipantToken: true,
    });
  },

  async getLeaderboard(gameId, limit = 10, roundId = null) {
    let url = `/api/v1/games/${gameId}/leaderboard?limit=${limit}`;

    if (roundId) {
      url += `&round_id=${roundId}`;
    }

    return apiRequest(url);
  },
};
