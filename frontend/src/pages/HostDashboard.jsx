import { useEffect, useState, useRef, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import { API_BASE_URL, hostApi, quizApi } from "../services/api";
import { QuizWebSocket } from "../services/websocket";

function HostDashboard() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const quizId = searchParams.get("quizId");
  const gameId = searchParams.get("gameId");

  const [quiz, setQuiz] = useState(null);
  const [game, setGame] = useState(null);
  const [players, setPlayers] = useState([]);
  const [status, setStatus] = useState("lobby");
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

  function applyGameSnapshot(snapshot) {
    if (!snapshot) return;
    setGame((previous) => ({
      ...(previous || {}),
      id: Number(gameId),
      quiz_id: Number(quizId),
      pin: snapshot.pin,
      status: snapshot.game_status || "lobby",
    }));
    setStatus(snapshot.game_status || "lobby");
    setPlayers(Array.isArray(snapshot.players) ? snapshot.players : []);
    setCurrentQuestion(snapshot.current_question || null);
    setQuestionNumber(Number(snapshot.question_number) || 1);
    setTotalQuestions(Number(snapshot.total_questions) || 1);
    setAnsweredCount(Number(snapshot.answered_count) || 0);
    setRevealedData(snapshot.revealed_data || null);
    setLeaderboard(snapshot.leaderboard?.top || []);
  }

  // Load quiz details and active game from the backend/session.
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

        const snapshot = await hostApi.getGameState(gameId);
        if (isMounted) applyGameSnapshot(snapshot);
      } catch (err) {
        console.error("Failed to load host initial data:", err);

        if (isMounted) {
          setError(err.message || "Failed to load game info.");
        }
      }
    }

    loadInitial();

    return () => {
      isMounted = false;
    };
  }, [quizId, gameId]);

  // Connect the host WebSocket.
  useEffect(() => {
    if (!gameId) return;

    const ws = new QuizWebSocket({
      role: "host",
      gameId,

      onOpen: () => {
        setWsConnected(true);
        hostApi.getGameState(gameId)
          .then(applyGameSnapshot)
          .catch((err) => console.warn("Could not refresh host game state:", err));
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
            if (
              prev.some(
                (p) => p.participant_id === data.participant_id
              )
            ) {
              return prev;
            }

            return [
              ...prev,
              {
                participant_id: data.participant_id,
                nickname: data.nickname,
              },
            ];
          });
        } else if (event === "PLAYER_LEFT") {
          setPlayers((prev) =>
            prev.filter(
              (p) => p.participant_id !== data.participant_id
            )
          );
        } else if (event === "PLAYER_KICKED") {
          setPlayers((prev) =>
            prev.filter(
              (p) => p.participant_id !== data.participant_id
            )
          );
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
          // Backend LeaderboardOut uses "top", not "entries".
          setLeaderboard(data.top || []);
        } else if (event === "GAME_FINISHED") {
          setStatus("finished");

          // GAME_FINISHED contains leaderboard inside data.leaderboard.
          setLeaderboard(data.leaderboard?.top || []);
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

  // Host action handlers.
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
    if (!window.confirm("Are you sure you want to end the game now?")) {
      return;
    }

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

  // Open projector with the backend-generated stage token.
  function handleOpenProjector() {
    const url = `/stage?gameId=${gameId}${
      stageToken ? `&token=${encodeURIComponent(stageToken)}` : ""
    }`;

    window.open(url, "quizvoro-projector");
  }

  const pin = game?.pin || "--------";
  const joinUrl = `${window.location.origin}/?pin=${pin}`;

  const isLobby = status === "lobby";
  const isActive = status === "active";
  const isPaused = status === "paused";
  const isReveal = status === "reveal";
  const isFinished = status === "finished";

  const stateLabel = isFinished
    ? "Quiz completed"
    : isReveal
      ? "Answer revealed"
      : isPaused
        ? "Quiz paused"
        : isActive
          ? `Question ${questionNumber} in progress`
          : "Waiting for players";

  if (error) {
    return (
      <main className="quiz-background flex min-h-screen items-center justify-center px-5 py-8 text-white">
        <div className="w-full max-w-lg rounded-3xl border border-white/10 bg-[#260638] p-8 text-center shadow-2xl">
          <h2 className="brand-font text-3xl font-bold">
            Unable to load game
          </h2>

          <p className="mt-4 leading-7 text-rose-200">
            {error}
          </p>

          <button
            type="button"
            onClick={() => navigate("/admin/quizzes")}
            className="mt-7 rounded-xl bg-[#E6D99D] px-6 py-3 font-bold text-[#321044] transition hover:bg-[#F2E5AB]"
          >
            BACK TO SAVED QUIZZES
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="quiz-background min-h-screen px-4 py-6 text-white sm:px-8 lg:px-10">
      <div className="mx-auto max-w-[1500px]">

        {/* Header */}
        <header className="mb-7 flex flex-wrap items-center justify-between gap-4 border-b border-white/15 pb-5">
          <div>
            <button
              type="button"
              onClick={() => navigate("/admin/dashboard")}
              className="brand-font text-3xl font-bold sm:text-4xl"
            >
              Asteris!
            </button>

            <p className="nav-font mt-1 text-xs font-bold tracking-[0.22em] text-[#91F0DF]">
              LIVE QUIZ HOSTING
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <span
              className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-bold ${
                wsConnected
                  ? "border-green-400/30 bg-green-400/10 text-green-300"
                  : "border-rose-400/30 bg-rose-400/10 text-rose-200"
              }`}
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  wsConnected ? "bg-green-400" : "bg-rose-400"
                }`}
              />
              {wsConnected ? "LIVE SYNC ON" : "CONNECTING..."}
            </span>

            <button
              type="button"
              onClick={handleOpenProjector}
              className="rounded-xl bg-[#E6D99D] px-4 py-3 text-sm font-bold text-[#321044] transition hover:bg-[#F2E5AB]"
            >
              OPEN PROJECTOR ↗
            </button>

            <button
              type="button"
              onClick={() => navigate("/admin/quizzes")}
              className="rounded-xl border border-white/30 px-4 py-3 text-sm font-bold transition hover:bg-white/10"
            >
              EXIT
            </button>
          </div>
        </header>

        {/* Quiz heading */}
        <section className="mb-6">
          <p className="nav-font text-xs font-bold tracking-[0.28em] text-[#91F0DF]">
            HOST CONTROL PANEL
          </p>

          <div className="mt-2 flex flex-wrap items-center gap-3">
            <h1 className="brand-font text-4xl font-bold sm:text-5xl">
              {quiz?.title || "Your Quiz"}
            </h1>

            <span className="rounded-full border border-white/20 bg-white/10 px-4 py-2 text-sm">
              {totalQuestions}{" "}
              {totalQuestions === 1 ? "question" : "questions"}
            </span>
          </div>

          <p className="mt-3 flex items-center gap-2 text-sm text-purple-100">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                isFinished
                  ? "bg-gray-300"
                  : isPaused
                    ? "bg-amber-400"
                    : isReveal
                      ? "bg-[#E6D99D]"
                      : "bg-[#91F0DF]"
              }`}
            />
            {stateLabel}
          </p>

          <p className="mt-2 max-w-3xl text-sm leading-6 text-purple-100/75">
            Manage your live quiz, monitor participants, control each
            question, and display results on the projector.
          </p>
        </section>

        {/* Host controls */}
        <section className="mb-6 rounded-2xl border border-[#A77BC5]/40 bg-[#260638]/90 p-5 shadow-xl sm:p-7">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="nav-font text-xs font-bold uppercase tracking-[0.2em] text-[#91F0DF]">
                HOST CONTROLS
              </p>

              <h2 className="brand-font mt-1 text-2xl sm:text-3xl">
                {isFinished
                  ? "Quiz completed"
                  : isReveal
                    ? "Answer and score revealed"
                    : isPaused
                      ? "Quiz is paused"
                      : isActive
                        ? `Question ${questionNumber} is live`
                        : "Ready to launch?"}
              </h2>

              <p className="mt-2 text-sm leading-6 text-purple-100/75">
                {isFinished
                  ? "The quiz has ended. Review the final leaderboard below."
                  : isReveal
                    ? "Review the answers and move to the next question when ready."
                    : isPaused
                      ? "The quiz is paused. Resume when you are ready."
                      : isActive
                        ? "Monitor answers and reveal the correct answer when ready."
                        : "Players can join using the PIN or QR code below. Start when everyone is ready."}
              </p>
            </div>

            {(isActive || isPaused || isReveal) && (
              <div className="rounded-xl border border-white/10 bg-white/10 px-5 py-3 text-center">
                <p className="text-xs tracking-wider text-purple-200">
                  PROGRESS
                </p>

                <p className="mt-1 text-2xl font-bold">
                  {questionNumber}
                  <span className="text-base font-normal text-purple-200">
                    {" "}/ {totalQuestions}
                  </span>
                </p>
              </div>
            )}
          </div>

          <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">

            {isLobby && (
              <button
                type="button"
                onClick={handleStartGame}
                disabled={actionLoading}
                className="min-h-[58px] rounded-xl bg-[#E6D99D] px-4 py-4 font-extrabold text-[#321044] transition hover:bg-[#F2E5AB] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {actionLoading ? "STARTING..." : "▶ START QUIZ"}
              </button>
            )}

            {isActive && (
              <button
                type="button"
                onClick={handlePause}
                disabled={actionLoading}
                className="min-h-[58px] rounded-xl bg-[#E6D99D] px-4 py-4 font-extrabold text-[#321044] transition hover:bg-[#F2E5AB] disabled:opacity-50"
              >
                ⏸ PAUSE QUIZ
              </button>
            )}

            {isPaused && (
              <button
                type="button"
                onClick={handleResume}
                disabled={actionLoading}
                className="min-h-[58px] rounded-xl bg-[#91F0DF] px-4 py-4 font-extrabold text-[#21052F] transition hover:bg-[#ACF7EA] disabled:opacity-50"
              >
                ▶ RESUME QUIZ
              </button>
            )}

            {(isActive || isPaused) && (
              <button
                type="button"
                onClick={handleReveal}
                disabled={actionLoading}
                className="min-h-[58px] rounded-xl bg-[#C51E50] px-4 py-4 font-extrabold text-white transition hover:bg-[#D92D62] disabled:opacity-50"
              >
                REVEAL ANSWER & SCORE
              </button>
            )}

            {isReveal && (
              <button
                type="button"
                onClick={handleNextQuestion}
                disabled={actionLoading}
                className="min-h-[58px] rounded-xl bg-[#91F0DF] px-4 py-4 font-extrabold text-[#21052F] transition hover:bg-[#ACF7EA] disabled:opacity-50"
              >
                NEXT QUESTION →
              </button>
            )}

            {!isFinished && (
              <button
                type="button"
                onClick={handleOpenProjector}
                className="min-h-[58px] rounded-xl border border-white/30 px-4 py-4 font-bold transition hover:bg-white/10"
              >
                OPEN PROJECTOR ↗
              </button>
            )}

            {!isLobby && !isFinished && (
              <button
                type="button"
                onClick={handleEndGame}
                disabled={actionLoading}
                className="min-h-[58px] rounded-xl border border-rose-300/70 px-4 py-4 font-bold text-rose-100 transition hover:bg-rose-500/15 disabled:opacity-50"
              >
                END QUIZ
              </button>
            )}
          </div>
        </section>

        {/* Main content and sidebar */}
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_350px]">

          {/* Main column */}
          <div className="min-w-0">

            {/* Join card */}
            {!isFinished && (
              <>
                <section className="grid gap-6 rounded-2xl bg-white p-5 text-[#321044] shadow-xl sm:p-7 md:grid-cols-[minmax(0,1fr)_150px_minmax(0,1fr)]">

                  <div>
                    <p className="nav-font text-xs font-bold tracking-widest text-purple-700">
                      PLAYERS JOIN HERE
                    </p>

                    <h2 className="brand-font mt-2 text-3xl">
                      Game PIN
                    </h2>

                    <div className="mt-4 rounded-xl bg-[#F0EAF7] px-3 py-5 text-center">
                      <p className="whitespace-nowrap text-3xl font-black tracking-widest sm:text-4xl">
                        {pin !== "--------"
                          ? `${pin.slice(0, 4)} ${pin.slice(4)}`
                          : "--------"}
                      </p>
                    </div>

                    <p className="mt-3 text-sm text-gray-500">
                      Enter this PIN on the Join page to participate.
                    </p>
                  </div>

                  <div className="flex flex-col items-center justify-center border-t border-gray-200 pt-5 md:border-l md:border-t-0 md:pl-5 md:pt-0">
                    <div className="rounded-xl border border-gray-200 p-2">
                      <QRCodeSVG
                        value={joinUrl}
                        size={112}
                        level="H"
                        includeMargin
                      />
                    </div>

                    <p className="mt-2 text-sm text-gray-600">
                      Scan to join
                    </p>
                  </div>

                  <div className="flex flex-col justify-center border-t border-gray-200 pt-5 md:border-l md:pl-5 md:pt-0">
                    <h3 className="font-bold">
                      Projector view
                    </h3>

                    <p className="mt-2 text-sm leading-5 text-gray-600">
                      Open a separate screen to display the live
                      question, results, and leaderboard.
                    </p>

                    <button
                      type="button"
                      onClick={handleOpenProjector}
                      className="nav-font mt-4 rounded-xl bg-[#321044] px-4 py-3 font-bold text-white transition hover:bg-[#49205C]"
                    >
                      OPEN PROJECTOR VIEW ↗
                    </button>
                  </div>
                </section>

                <div className="mt-4 rounded-xl border border-white/10 bg-white/10 p-4 text-sm text-purple-100">
                  Players join using the PIN or QR code. Their joining
                  activity is synchronized through the live connection.
                </div>
              </>
            )}

            {/* Lobby players */}
            {isLobby && (
              <section className="mt-6 rounded-2xl bg-white p-5 text-[#321044] shadow-xl sm:p-7">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200 pb-4">
                  <h2 className="brand-font text-2xl">
                    Players in Lobby
                  </h2>

                  <span className="rounded-full bg-purple-100 px-3 py-1 text-sm font-bold text-purple-800">
                    {players.length} joined
                  </span>
                </div>

                {players.length === 0 ? (
                  <p className="py-8 text-center text-gray-500">
                    No participants have joined yet. Share the PIN to
                    invite players.
                  </p>
                ) : (
                  <div className="mt-5 flex max-h-72 flex-wrap gap-3 overflow-y-auto">
                    {players.map((player) => (
                      <div
                        key={player.participant_id}
                        className="flex items-center gap-3 rounded-xl bg-[#F0EAF7] px-4 py-3 font-semibold"
                      >
                        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[#321044] text-sm text-white">
                          {player.nickname?.charAt(0)?.toUpperCase() || "P"}
                        </span>

                        <span>{player.nickname}</span>

                        <button
                          type="button"
                          onClick={() =>
                            handleKickPlayer(player.participant_id)
                          }
                          className="ml-1 text-sm font-bold text-red-500 transition hover:text-red-700"
                          title="Remove player"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            )}

            {/* Current question */}
            {(isActive || isPaused || isReveal) && (
              <section className="mt-6 rounded-2xl bg-white p-5 text-[#321044] shadow-xl sm:p-7">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200 pb-4">
                  <span className="rounded-full bg-purple-100 px-3 py-2 text-sm font-bold text-[#321044]">
                    QUESTION {questionNumber} OF {totalQuestions}
                  </span>

                  <span className="rounded-full bg-[#F0EAF7] px-3 py-2 text-sm font-bold text-purple-800">
                    {answeredCount} ANSWERED
                  </span>
                </div>

                <div className="mt-6">
                  <p className="nav-font text-xs font-bold tracking-widest text-purple-600">
                    CURRENT QUESTION
                  </p>

                  <h2 className="brand-font mt-3 text-2xl font-bold leading-snug sm:text-3xl">
                    {currentQuestion?.question_text || "Current Question"}
                  </h2>

                  {currentQuestion?.media_url && (() => {
                    const mediaUrl = /^https?:\/\//i.test(currentQuestion.media_url)
                      ? currentQuestion.media_url
                      : `${API_BASE_URL.replace(/\/$/, "")}${currentQuestion.media_url.startsWith("/") ? "" : "/"}${currentQuestion.media_url}`;
                    const mediaType = String(currentQuestion.media_type || "").toLowerCase();

                    if (mediaType === "video") {
                      return (
                        <video controls playsInline preload="metadata" className="mt-5 max-h-80 w-full rounded-xl bg-black object-contain" src={mediaUrl}>
                          Your browser cannot play this video format.
                        </video>
                      );
                    }
                    if (mediaType === "audio") {
                      return <audio controls preload="metadata" className="mt-5 w-full" src={mediaUrl} />;
                    }
                    if (mediaType === "image") {
                      return <img src={mediaUrl} alt="Question media" className="mx-auto mt-5 max-h-80 max-w-full rounded-xl object-contain" />;
                    }
                    return null;
                  })()}
                </div>

                <div className="mt-7 grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {currentQuestion?.options?.map((option, index) => {
                    const isCorrect =
                      revealedData?.correct_option_id === option.id;

                    const voteCount =
                      revealedData?.distribution?.find(
                        (item) => item.option_id === option.id
                      )?.count || 0;

                    return (
                      <div
                        key={option.id}
                        className={`flex items-center justify-between gap-3 rounded-xl border-2 p-4 transition ${
                          isReveal && isCorrect
                            ? "border-green-500 bg-green-50"
                            : isReveal
                              ? "border-gray-200 bg-gray-50"
                              : "border-gray-200 bg-[#FAF9FD]"
                        }`}
                      >
                        <div className="flex min-w-0 items-center gap-3">
                          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#321044] text-sm font-bold text-white">
                            {String.fromCharCode(65 + index)}
                          </span>

                          <span className="break-words font-semibold">
                            {option.option_text}
                          </span>
                        </div>

                        {isReveal && (
                          <span className="shrink-0 text-sm font-bold text-gray-600">
                            {voteCount} votes
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>

                {isPaused && (
                  <p className="mt-5 rounded-xl bg-amber-50 p-4 text-sm font-semibold text-amber-800">
                    The quiz is paused. Resume the quiz when you are ready.
                  </p>
                )}

                {isReveal && (
                  <p className="mt-5 rounded-xl bg-green-50 p-4 text-sm font-semibold text-green-800">
                    The answer has been revealed. You can proceed to the
                    next question.
                  </p>
                )}
              </section>
            )}

            {/* Final leaderboard */}
            {isFinished && (
              <section className="rounded-2xl bg-white p-5 text-[#321044] shadow-xl sm:p-7">
                <div className="text-center">
                  <span className="text-5xl">🏆</span>

                  <h2 className="brand-font mt-3 text-3xl font-bold sm:text-4xl">
                    Quiz Complete!
                  </h2>

                  <p className="mt-2 text-gray-500">
                    Final Leaderboard Standings
                  </p>
                </div>

                <div className="mx-auto mt-8 max-w-2xl space-y-3">
                  {leaderboard.length === 0 ? (
                    <p className="py-6 text-center text-gray-500">
                      No scores recorded.
                    </p>
                  ) : (
                    leaderboard.map((entry, index) => (
                      <div
                        key={entry.participant_id}
                        className={`flex items-center justify-between gap-3 rounded-xl border p-4 ${
                          index === 0
                            ? "border-amber-300 bg-amber-100"
                            : index === 1
                              ? "border-gray-300 bg-gray-100"
                              : index === 2
                                ? "border-amber-200 bg-amber-50"
                                : "border-gray-200 bg-white"
                        }`}
                      >
                        <div className="flex min-w-0 items-center gap-4">
                          <span className="w-9 shrink-0 text-center text-xl font-extrabold">
                            #{entry.rank}
                          </span>

                          <span className="truncate font-semibold">
                            {entry.nickname}
                          </span>
                        </div>

                        <span className="shrink-0 font-bold text-[#C51E50]">
                          {entry.score} pts
                        </span>
                      </div>
                    ))
                  )}
                </div>

                <button
                  type="button"
                  onClick={() => navigate("/admin/quizzes")}
                  className="mt-8 w-full rounded-xl bg-[#321044] px-6 py-4 font-bold text-white transition hover:bg-[#49205C]"
                >
                  BACK TO QUIZZES
                </button>
              </section>
            )}
          </div>

          {/* Right sidebar */}
          <aside className="space-y-5">

            {/* Live status */}
            <section className="rounded-2xl border border-white/10 bg-[#260638]/85 p-6 shadow-xl">
              <h2 className="brand-font text-2xl">
                Live status
              </h2>

              <div className="mt-4 rounded-xl bg-white p-4 text-[#321044]">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm text-gray-500">
                      Players joined
                    </p>

                    <p className="mt-1 text-3xl font-bold">
                      {players.length}
                    </p>
                  </div>

                  <span
                    className={`rounded-full px-3 py-2 text-xs font-bold ${
                      isFinished
                        ? "bg-gray-100 text-gray-700"
                        : isPaused
                          ? "bg-amber-100 text-amber-800"
                          : isReveal
                            ? "bg-purple-100 text-purple-800"
                            : isActive
                              ? "bg-green-100 text-green-800"
                              : "bg-[#F0EAF7] text-purple-800"
                    }`}
                  >
                    {isFinished
                      ? "FINISHED"
                      : isPaused
                        ? "PAUSED"
                        : isReveal
                          ? "REVEALED"
                          : isActive
                            ? "IN PROGRESS"
                            : "WAITING"}
                  </span>
                </div>
              </div>

              <div className="mt-4 flex items-center justify-between text-sm">
                <span className="text-purple-100/70">
                  Answered
                </span>

                <span className="font-bold">
                  {answeredCount}
                </span>
              </div>

              <div className="mt-3 flex items-center justify-between text-sm">
                <span className="text-purple-100/70">
                  WebSocket
                </span>

                <span
                  className={
                    wsConnected ? "font-bold text-green-300" : "font-bold text-rose-300"
                  }
                >
                  {wsConnected ? "Connected" : "Disconnected"}
                </span>
              </div>
            </section>

            {/* Quiz settings */}
            <section className="rounded-2xl border border-white/10 bg-[#260638]/85 p-6 shadow-xl">
              <h2 className="brand-font text-xl">
                Quiz settings
              </h2>

              <div className="mt-4 space-y-4 text-sm">
                <div className="flex items-start justify-between gap-3">
                  <span className="text-purple-100/70">
                    Quiz name
                  </span>

                  <span className="max-w-[60%] break-words text-right font-semibold">
                    {quiz?.title || "Quiz"}
                  </span>
                </div>

                <div className="flex items-center justify-between gap-3">
                  <span className="text-purple-100/70">
                    Game PIN
                  </span>

                  <span className="font-bold tracking-wider">
                    {pin}
                  </span>
                </div>

                <div className="flex items-center justify-between gap-3">
                  <span className="text-purple-100/70">
                    Current question
                  </span>

                  <span className="font-semibold">
                    {isLobby ? "-" : `${questionNumber}/${totalQuestions}`}
                  </span>
                </div>

                <div className="flex items-center justify-between gap-3">
                  <span className="text-purple-100/70">
                    Game status
                  </span>

                  <span className="font-semibold capitalize">
                    {status}
                  </span>
                </div>
              </div>
            </section>

            {/* Leaderboard preview */}
            {(isReveal || isFinished) && (
              <section className="rounded-2xl border border-white/10 bg-[#260638]/85 p-6 shadow-xl">
                <h2 className="brand-font text-xl">
                  {isFinished ? "Final leaderboard" : "Leaderboard"}
                </h2>

                {leaderboard.length === 0 ? (
                  <p className="mt-4 text-sm text-purple-100/70">
                    Leaderboard data will appear when received from the
                    server.
                  </p>
                ) : (
                  <div className="mt-4 space-y-3">
                    {leaderboard.slice(0, 5).map((entry) => (
                      <div
                        key={entry.participant_id}
                        className="flex items-center justify-between gap-3 rounded-lg bg-white/10 px-3 py-3 text-sm"
                      >
                        <span className="min-w-0 truncate">
                          <span className="mr-2 font-bold text-[#E6D99D]">
                            #{entry.rank}
                          </span>
                          {entry.nickname}
                        </span>

                        <span className="shrink-0 font-bold text-[#91F0DF]">
                          {entry.score}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            )}

            <button
              type="button"
              onClick={() => navigate("/admin/quizzes")}
              className="nav-font w-full rounded-xl border border-white/20 bg-white/5 px-5 py-3 font-bold transition hover:bg-white/10"
            >
              ← BACK TO QUIZ LIST
            </button>
          </aside>
        </div>
      </div>
    </main>
  );
}

export default HostDashboard;
