import { useEffect, useState, useRef, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import { hostApi, quizApi } from "../services/api";
import { QuizWebSocket } from "../services/websocket";

function HostDashboard() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const quizId = searchParams.get("quizId");
  const gameId = searchParams.get("gameId");

  const [quiz, setQuiz] = useState(null);
  const [game, setGame] = useState(null);
  const [players, setPlayers] = useState([]);
  const [status, setStatus] = useState("lobby"); // lobby, active, paused, reveal, finished
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [questionNumber, setQuestionNumber] = useState(1);
  const [totalQuestions, setTotalQuestions] = useState(1);
  const [answeredCount, setAnsweredCount] = useState(0);
  const [revealedData, setRevealedData] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [stageToken, setStageToken] = useState("");
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  const wsRef = useRef(null);

  // Load quiz details and active game
  useEffect(() => {
    if (!quizId || !gameId) {
      setError("Missing quizId or gameId in query parameters.");
      return;
    }

    let isMounted = true;

    async function loadInitial() {
      try {
        const quizData = await quizApi.getQuiz(quizId);
        if (isMounted) setQuiz(quizData);

        const tokenData = await hostApi.getStageToken(gameId);
        if (isMounted) setStageToken(tokenData.stage_token);

        const rawGame = sessionStorage.getItem("quizvoro_active_game");
        if (rawGame && isMounted) {
          const parsed = JSON.parse(rawGame);
          setGame(parsed);
          setStatus(parsed.status || "lobby");
        }
      } catch (err) {
        console.error("Failed to load host initial data:", err);
        if (isMounted) setError(err.message || "Failed to load game info.");
      }
    }

    loadInitial();
    return () => {
      isMounted = false;
    };
  }, [quizId, gameId]);

  // Connect Host WebSocket
  useEffect(() => {
    if (!gameId) return;

    const ws = new QuizWebSocket({
      role: "host",
      gameId,
      onOpen: () => {
        setWsConnected(true);
      },
      onClose: () => {
        setWsConnected(false);
      },
      onError: (err) => {
        console.warn("Host WS error:", err);
      },
      onMessage: (event, data) => {
        if (event === "PLAYER_JOINED") {
          setPlayers((prev) => {
            if (prev.some((p) => p.participant_id === data.participant_id)) return prev;
            return [...prev, { participant_id: data.participant_id, nickname: data.nickname }];
          });
        } else if (event === "PLAYER_LEFT") {
          setPlayers((prev) => prev.filter((p) => p.participant_id !== data.participant_id));
        } else if (event === "PLAYER_KICKED") {
          setPlayers((prev) => prev.filter((p) => p.participant_id !== data.participant_id));
        } else if (event === "QUESTION_STARTED") {
          setStatus("active");
          setCurrentQuestion(data.question);
          setQuestionNumber(data.question_number);
          setTotalQuestions(data.total_questions);
          setAnsweredCount(0);
          setRevealedData(null);
        } else if (event === "ANSWER_COUNT_UPDATED") {
          setAnsweredCount(data.answered_count);
        } else if (event === "GAME_PAUSED") {
          setStatus("paused");
        } else if (event === "GAME_RESUMED") {
          setStatus("active");
        } else if (event === "ANSWER_REVEALED") {
          setStatus("reveal");
          setRevealedData(data);
        } else if (event === "LEADERBOARD_UPDATED") {
          setLeaderboard(data.entries || []);
        } else if (event === "GAME_FINISHED") {
          setStatus("finished");
        } else if (event === "ERROR") {
          console.error("Host error event:", data);
        }
      },
    });

    ws.connect();
    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, [gameId]);

  // Host Action Handlers
  const handleStartGame = useCallback(async () => {
    setActionLoading(true);
    try {
      if (wsRef.current && wsConnected) {
        wsRef.current.sendHostAction("START");
      } else {
        await hostApi.startGame(gameId);
      }
    } catch (err) {
      alert(err.message || "Failed to start quiz.");
    } finally {
      setActionLoading(false);
    }
  }, [gameId, wsConnected]);

  const handleNextQuestion = useCallback(async () => {
    setActionLoading(true);
    try {
      if (wsRef.current && wsConnected) {
        wsRef.current.sendHostAction("NEXT_QUESTION");
      } else {
        await hostApi.nextQuestion(gameId);
      }
    } catch (err) {
      alert(err.message || "Failed to proceed to next question.");
    } finally {
      setActionLoading(false);
    }
  }, [gameId, wsConnected]);

  const handlePause = useCallback(async () => {
    setActionLoading(true);
    try {
      if (wsRef.current && wsConnected) {
        wsRef.current.sendHostAction("PAUSE");
      } else {
        await hostApi.pauseGame(gameId);
      }
    } catch (err) {
      alert(err.message || "Failed to pause.");
    } finally {
      setActionLoading(false);
    }
  }, [gameId, wsConnected]);

  const handleResume = useCallback(async () => {
    setActionLoading(true);
    try {
      if (wsRef.current && wsConnected) {
        wsRef.current.sendHostAction("RESUME");
      } else {
        await hostApi.resumeGame(gameId);
      }
    } catch (err) {
      alert(err.message || "Failed to resume.");
    } finally {
      setActionLoading(false);
    }
  }, [gameId, wsConnected]);

  const handleReveal = useCallback(async () => {
    setActionLoading(true);
    try {
      if (wsRef.current && wsConnected) {
        wsRef.current.sendHostAction("REVEAL");
      } else {
        await hostApi.revealAnswer(gameId);
      }
    } catch (err) {
      alert(err.message || "Failed to reveal answers.");
    } finally {
      setActionLoading(false);
    }
  }, [gameId, wsConnected]);

  const handleEndGame = useCallback(async () => {
    if (!window.confirm("Are you sure you want to end the game now?")) return;
    setActionLoading(true);
    try {
      if (wsRef.current && wsConnected) {
        wsRef.current.sendHostAction("END");
      } else {
        await hostApi.endGame(gameId);
      }
      setStatus("finished");
    } catch (err) {
      alert(err.message || "Failed to end game.");
    } finally {
      setActionLoading(false);
    }
  }, [gameId, wsConnected]);

  const handleKickPlayer = useCallback(
    async (pId) => {
      try {
        if (wsRef.current && wsConnected) {
          wsRef.current.sendHostAction("KICK", pId);
        } else {
          await hostApi.kickParticipant(gameId, pId);
        }
      } catch (err) {
        alert(err.message || "Failed to remove player.");
      }
    },
    [gameId, wsConnected]
  );

  function handleOpenProjector() {
    const url = `/stage?gameId=${gameId}${stageToken ? `&token=${encodeURIComponent(stageToken)}` : ""}`;
    window.open(url, "quizvoro-projector");
  }

  const pin = game?.pin || "--------";
  const joinUrl = `${window.location.origin}/?pin=${pin}`;

  if (error) {
    return (
      <main className="quiz-background flex min-h-screen flex-col items-center justify-center p-6 text-white">
        <h2 className="text-2xl font-bold mb-4">Error loading game</h2>
        <p className="text-red-300 mb-6">{error}</p>
        <button
          onClick={() => navigate("/admin/quizzes")}
          className="rounded-xl bg-[#91F0DF] px-6 py-3 font-bold text-[#31064D]"
        >
          Back to Saved Quizzes
        </button>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-4 py-8 text-[#31064D] sm:px-8">
      <div className="mx-auto max-w-6xl">
        {/* Top bar */}
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-white/20 pb-6 text-white">
          <div>
            <span className="text-xs font-bold tracking-widest text-[#91F0DF] uppercase">
              LIVE HOST CONTROLLER
            </span>
            <h1 className="brand-font text-3xl font-bold sm:text-4xl">
              {quiz?.title || "Quiz"}
            </h1>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold ${
              wsConnected ? "bg-green-500/20 text-green-300" : "bg-red-500/20 text-red-300"
            }`}>
              <span className={`h-2 w-2 rounded-full ${wsConnected ? "bg-green-400" : "bg-red-400"}`} />
              {wsConnected ? "LIVE SYNC ON" : "CONNECTING..."}
            </span>

            <button
              type="button"
              onClick={handleOpenProjector}
              className="rounded-xl bg-[#E6D99D] px-4 py-2.5 font-bold text-[#31064D] hover:bg-[#F2E5AB]"
            >
              📺 OPEN PROJECTOR
            </button>

            <button
              type="button"
              onClick={() => navigate("/admin/quizzes")}
              className="rounded-xl border border-white/40 px-4 py-2.5 font-bold text-white hover:bg-white/10"
            >
              EXIT
            </button>
          </div>
        </header>

        {/* Status / Controller Cards */}
        {status === "lobby" && (
          <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* PIN & QR Card */}
            <div className="rounded-3xl bg-white p-8 shadow-2xl lg:col-span-1 text-center">
              <p className="text-xs font-bold tracking-widest text-gray-500 uppercase">
                JOIN PIN
              </p>
              <p className="brand-font my-2 text-5xl font-extrabold tracking-widest text-[#31064D]">
                {pin}
              </p>
              <div className="my-6 flex justify-center">
                <QRCodeSVG value={joinUrl} size={180} />
              </div>
              <p className="text-xs text-gray-500">
                Join at <span className="font-semibold">{window.location.origin}</span>
              </p>
            </div>

            {/* Players Lobby Card */}
            <div className="rounded-3xl bg-white p-8 shadow-2xl lg:col-span-2 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between border-b pb-4">
                  <h2 className="text-2xl font-bold text-[#31064D]">
                    Players in Lobby ({players.length})
                  </h2>
                  <span className="text-sm font-semibold text-purple-700">
                    Waiting for players to join...
                  </span>
                </div>

                <div className="mt-6 flex flex-wrap gap-2.5 max-h-64 overflow-y-auto">
                  {players.length === 0 ? (
                    <p className="text-gray-400 italic py-8">
                      No participants have joined yet. Tell players to enter PIN {pin}.
                    </p>
                  ) : (
                    players.map((p) => (
                      <div
                        key={p.participant_id}
                        className="flex items-center gap-2 rounded-xl bg-[#F0EFF2] px-3.5 py-2 font-semibold text-[#31064D]"
                      >
                        <span>{p.nickname}</span>
                        <button
                          type="button"
                          onClick={() => handleKickPlayer(p.participant_id)}
                          className="text-xs text-red-500 hover:text-red-700 ml-1 font-bold"
                          title="Kick player"
                        >
                          ✕
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="mt-8 border-t pt-6 flex justify-end">
                <button
                  type="button"
                  disabled={actionLoading}
                  onClick={handleStartGame}
                  className="rounded-2xl bg-[#91F0DF] px-8 py-4 text-xl font-bold text-[#31064D] shadow-lg transition hover:brightness-105 disabled:opacity-50"
                >
                  {actionLoading ? "STARTING..." : "START QUIZ NOW 🚀"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Live Question / Controls Active */}
        {(status === "active" || status === "paused" || status === "reveal") && (
          <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* Current Question Info */}
            <div className="rounded-3xl bg-white p-8 shadow-2xl lg:col-span-2">
              <div className="flex items-center justify-between border-b pb-4">
                <span className="rounded-full bg-purple-100 px-3 py-1 font-bold text-sm text-[#31064D]">
                  Question {questionNumber} of {totalQuestions}
                </span>
                <span className="text-sm font-semibold text-gray-500">
                  {answeredCount} answered
                </span>
              </div>

              <h2 className="mt-6 text-2xl font-bold leading-snug sm:text-3xl text-[#31064D]">
                {currentQuestion?.question_text || "Current Question"}
              </h2>

              {/* Options display */}
              <div className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2">
                {currentQuestion?.options?.map((opt, idx) => {
                  const isRevealed = status === "reveal";
                  const isCorrect = revealedData?.correct_option_id === opt.id;
                  const count =
                    revealedData?.distribution?.find((d) => d.option_id === opt.id)?.count || 0;

                  return (
                    <div
                      key={opt.id}
                      className={`flex items-center justify-between rounded-2xl border-2 p-4 transition ${
                        isRevealed && isCorrect
                          ? "border-green-500 bg-green-50"
                          : isRevealed
                          ? "border-gray-200 bg-gray-50 opacity-70"
                          : "border-gray-200 bg-[#FAF9FD]"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#31064D] font-bold text-white text-sm">
                          {String.fromCharCode(65 + idx)}
                        </span>
                        <span className="font-semibold text-[#31064D]">
                          {opt.option_text}
                        </span>
                      </div>
                      {isRevealed && (
                        <span className="font-bold text-sm text-gray-600">
                          {count} votes
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Host Control Actions */}
            <div className="rounded-3xl bg-white p-8 shadow-2xl lg:col-span-1 flex flex-col justify-between">
              <div>
                <h3 className="text-xl font-bold text-[#31064D] border-b pb-4">
                  Host Controls
                </h3>
                <p className="mt-3 text-sm text-gray-500">
                  Status: <strong className="uppercase text-[#31064D]">{status}</strong>
                </p>
              </div>

              <div className="space-y-3 mt-6">
                {status === "active" && (
                  <button
                    type="button"
                    disabled={actionLoading}
                    onClick={handlePause}
                    className="w-full rounded-xl bg-amber-500 py-3.5 font-bold text-white shadow transition hover:bg-amber-600 disabled:opacity-50"
                  >
                    ⏸ PAUSE TIMER
                  </button>
                )}

                {status === "paused" && (
                  <button
                    type="button"
                    disabled={actionLoading}
                    onClick={handleResume}
                    className="w-full rounded-xl bg-green-600 py-3.5 font-bold text-white shadow transition hover:bg-green-700 disabled:opacity-50"
                  >
                    ▶ RESUME TIMER
                  </button>
                )}

                {status !== "reveal" && (
                  <button
                    type="button"
                    disabled={actionLoading}
                    onClick={handleReveal}
                    className="w-full rounded-xl bg-[#C51E50] py-3.5 font-bold text-white shadow transition hover:bg-[#D6295D] disabled:opacity-50"
                  >
                    👁 REVEAL ANSWER & SCORE
                  </button>
                )}

                {status === "reveal" && (
                  <button
                    type="button"
                    disabled={actionLoading}
                    onClick={handleNextQuestion}
                    className="w-full rounded-2xl bg-[#91F0DF] py-4 text-lg font-bold text-[#31064D] shadow-lg transition hover:brightness-105 disabled:opacity-50"
                  >
                    NEXT QUESTION →
                  </button>
                )}

                <button
                  type="button"
                  disabled={actionLoading}
                  onClick={handleEndGame}
                  className="w-full rounded-xl border border-red-300 py-3 font-semibold text-red-600 hover:bg-red-50 disabled:opacity-50"
                >
                  End Quiz Now
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Finished / Final Leaderboard */}
        {status === "finished" && (
          <div className="mt-8 rounded-3xl bg-white p-8 shadow-2xl">
            <div className="text-center">
              <span className="text-5xl">🏆</span>
              <h2 className="brand-font mt-2 text-4xl font-bold text-[#31064D]">
                Quiz Complete!
              </h2>
              <p className="mt-2 text-gray-600">
                Final Leaderboard Standings
              </p>
            </div>

            <div className="mt-8 max-w-2xl mx-auto space-y-3">
              {leaderboard.length === 0 ? (
                <p className="text-center text-gray-500 py-6">
                  No scores recorded.
                </p>
              ) : (
                leaderboard.map((entry, idx) => (
                  <div
                    key={entry.participant_id}
                    className={`flex items-center justify-between rounded-2xl p-4 shadow-sm border ${
                      idx === 0
                        ? "bg-amber-100 border-amber-300 font-bold"
                        : idx === 1
                        ? "bg-gray-100 border-gray-300 font-bold"
                        : idx === 2
                        ? "bg-amber-50 border-amber-200 font-bold"
                        : "bg-white border-gray-200"
                    }`}
                  >
                    <div className="flex items-center gap-4">
                      <span className="text-xl font-extrabold w-8 text-center text-[#31064D]">
                        #{entry.rank}
                      </span>
                      <span className="text-lg text-[#31064D]">
                        {entry.nickname}
                      </span>
                    </div>
                    <span className="text-lg font-bold text-[#C51E50]">
                      {entry.score} pts
                    </span>
                  </div>
                ))
              )}
            </div>

            <div className="mt-10 text-center">
              <button
                type="button"
                onClick={() => navigate("/admin/quizzes")}
                className="rounded-xl bg-[#31064D] px-8 py-3.5 font-bold text-white transition hover:bg-[#49205C]"
              >
                BACK TO QUIZZES
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

export default HostDashboard;
