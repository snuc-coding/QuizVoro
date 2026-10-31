// Centralized WebSocket Manager for Host, Participant, and Stage clients

import { WS_BASE_URL, getAdminToken, getParticipantToken } from "./api";

export class QuizWebSocket {
  /**
   * @param {Object} options
   * @param {string} options.role 'host' | 'participant' | 'stage'
   * @param {number|string} options.gameId
   * @param {string} [options.token] Optional explicit token (if not provided, retrieved from storage or stageToken)
   * @param {Function} [options.onMessage] (event, data, raw) => void
   * @param {Function} [options.onOpen] () => void
   * @param {Function} [options.onClose] (event) => void
   * @param {Function} [options.onError] (error) => void
   */
  constructor({ role, gameId, token = null, onMessage, onOpen, onClose, onError }) {
    this.role = role;
    this.gameId = gameId;
    this.token = token;
    this.onMessage = onMessage || (() => {});
    this.onOpen = onOpen || (() => {});
    this.onClose = onClose || (() => {});
    this.onError = onError || (() => {});

    this.ws = null;
    this.pingTimer = null;
    this.reconnectTimer = null;
    this.isManualClosed = false;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
  }

  connect() {
    this.isManualClosed = false;

    // Determine authorization token based on role
    let authToken = this.token;
    if (!authToken) {
      if (this.role === "host") {
        authToken = getAdminToken();
      } else if (this.role === "participant") {
        authToken = getParticipantToken();
      }
    }

    if (!authToken) {
      const err = new Error(`Cannot connect ${this.role} WebSocket without authentication token.`);
      this.onError(err);
      return;
    }

    const endpoint = `${WS_BASE_URL}/api/v1/ws/games/${this.gameId}/${this.role}?token=${encodeURIComponent(
      authToken
    )}`;

    try {
      this.ws = new WebSocket(endpoint);
    } catch (err) {
      this.onError(err);
      this._scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this._startPing();
      this.onOpen();
    };

    this.ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        const eventType = payload.event;
        const data = payload.data || {};
        this.onMessage(eventType, data, payload);
      } catch (err) {
        console.error("Failed to parse WebSocket message:", event.data, err);
      }
    };

    this.ws.onerror = (err) => {
      this.onError(err);
    };

    this.ws.onclose = (event) => {
      this._stopPing();
      this.onClose(event);
      if (!this.isManualClosed) {
        this._scheduleReconnect();
      }
    };
  }

  _startPing() {
    this._stopPing();
    this.pingTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ event: "PING" }));
      }
    }, 25000);
  }

  _stopPing() {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  _scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.warn(`WebSocket reached max reconnect attempts (${this.maxReconnectAttempts}).`);
      return;
    }

    const delay = Math.min(1000 * Math.pow(1.5, this.reconnectAttempts), 10000);
    this.reconnectAttempts += 1;

    clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => {
      if (!this.isManualClosed) {
        this.connect();
      }
    }, delay);
  }

  // Send host control command
  sendHostAction(action, participantId = null) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket is not connected.");
    }
    const payload = { action };
    if (participantId !== null && participantId !== undefined) {
      payload.participant_id = Number(participantId);
    }
    this.ws.send(JSON.stringify(payload));
  }

  // Send participant answer via WebSocket
  sendAnswer({ question_id, option_id = null, selected_option = null }) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket is not connected.");
    }
    this.ws.send(
      JSON.stringify({
        event: "SUBMIT_ANSWER",
        data: {
          question_id: Number(question_id),
          option_id: option_id !== null ? Number(option_id) : null,
          selected_option: selected_option !== null ? selected_option : null,
        },
      })
    );
  }

  close() {
    this.isManualClosed = true;
    this._stopPing();
    clearTimeout(this.reconnectTimer);
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
