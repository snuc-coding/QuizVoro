
import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useLocation, useNavigate } from "react-router-dom";
import {
  participantApi,
  getParticipantSession,
  API_BASE_URL,
} from "../services/api";
import { QuizWebSocket } from "../services/websocket";

const optionColors = [
  {
    card: "bg-amber-400 hover:bg-amber-500",
    text: "text-[#21152C]",
    letter: "bg-amber-950/20",
  },
  {
    card: "bg-cyan-400 hover:bg-cyan-500",
    text: "text-[#071923]",
    letter: "bg-cyan-950/20",
  },
  {
    card: "bg-lime-400 hover:bg-lime-500",
    text: "text-[#19200B]",
    letter: "bg-lime-950/20",
  },
  {
    card: "bg-rose-400 hover:bg-rose-500",
    text: "text-white",
    letter: "bg-rose-950/20",
  },
];

function readParticipantScreenState(storageKey) {
  try {
    if (typeof window === "undefined") return null;
    const saved = window.sessionStorage.getItem(storageKey);
    return saved ? JSON.parse(saved) : null;
  } catch (error) {
    console.warn("Could not read saved participant state:", error);
    return null;
  }
}

function QuestionScreen() {
  const { gameId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  const participantData =
    location.state || getParticipantSession() || {};

  const token = participantData.token;
  const nickname = participantData.nickname || "Player";

  // Keep this state per game and participant, and per browser tab.
  const storageKey = `quizvoro:participant-screen:${gameId}:${nickname}`;
  const [savedState] = useState(() =>
    readParticipantScreenState(storageKey)
  );

  const [gameState, setGameState] = useState(
    savedState?.gameState || "lobby"
  );
  const [currentQuestion, setCurrentQuestion] = useState(
    savedState?.currentQuestion || null
  );
  const [questionNumber, setQuestionNumber] = useState(
    savedState?.questionNumber || 1
  );
  const [totalQuestions, setTotalQuestions] = useState(
    savedState?.totalQuestions || 1
  );
  const [timeLeft, setTimeLeft] = useState(
    savedState?.timeLeft ?? 15
  );
  const [selectedOptionId, setSelectedOptionId] = useState(
    savedState?.selectedOptionId ?? null
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [answerLocked, setAnswerLocked] = useState(
    savedState?.answerLocked ?? false
  );
  const [myResult, setMyResult] = useState(
    savedState?.myResult || null
  );
  const [error, setError] = useState("");
  const [answerError, setAnswerError] = useState("");
  const [leaderboard, setLeaderboard] = useState(savedState?.leaderboard || []);
  const [revealedData, setRevealedData] = useState(savedState?.revealedData || null);

  const wsRef = useRef(null);
  const timerRef = useRef(null);

  // Persist the participant's screen so a refresh does not send them to lobby.
  useEffect(() => {
    if (!token) return;

    const snapshot = {
      gameState,
      currentQuestion,
      questionNumber,
      totalQuestions,
      timeLeft,
      selectedOptionId,
      answerLocked,
      myResult,
      leaderboard,
      revealedData,
    };

    try {
      window.sessionStorage.setItem(storageKey, JSON.stringify(snapshot));
    } catch (storageError) {
      console.warn("Could not save participant screen state:", storageError);
    }
  }, [
    token,
    storageKey,
    gameState,
    currentQuestion,
    questionNumber,
    totalQuestions,
    timeLeft,
    selectedOptionId,
    answerLocked,
    myResult,
    leaderboard,
    revealedData,
  ]);

  // Start an accurate countdown using a local target time.
  const startCountdown = useCallback((seconds) => {
    clearInterval(timerRef.current);

    const duration = Math.max(0, Number(seconds) || 0);
    const targetTime = Date.now() + duration * 1000;

    setTimeLeft(Math.ceil(duration));

    timerRef.current = setInterval(() => {
      const remaining = Math.max(0, (targetTime - Date.now()) / 1000);

      setTimeLeft(Math.ceil(remaining));

      if (remaining <= 0) {
        clearInterval(timerRef.current);
      }
    }, 200);
  }, []);

  // Build a media URL that works for both relative and absolute URLs.
  const getMediaUrl = (url) => {
    if (!url) return "";

    if (/^https?:\/\//i.test(url)) {
      return url;
    }

    return `${API_BASE_URL.replace(/\/$/, "")}${
      url.startsWith("/") ? "" : "/"
    }${url}`;
  };

  // Connect Participant WebSocket and restore an existing live question.
  useEffect(() => {
    if (!gameId || !token) {
      setError(
        "No active participant session found. Please join from the home screen."
      );
      return;
    }

    let cancelled = false;

    // Restore from the backend first. If the game is in reveal/paused/finished
    // state, the current-question endpoint may return 409, so retain the saved
    // screen and retrieve the participant's latest score separately.
    const restoreParticipantState = async () => {
      const savedQuestionId = savedState?.currentQuestion?.id;

      try {
        const data = await participantApi.getCurrentQuestion(gameId);

        if (cancelled || !data) return;

        const restoredQuestion = data.question;
        if (!restoredQuestion) return;

        const sameQuestion =
          savedQuestionId != null &&
          String(savedQuestionId) === String(restoredQuestion.id);

        // Do not turn a previously displayed reveal back into "answered"
        // when the backend still returns the same question.
        if (
          sameQuestion &&
          (savedState?.gameState === "reveal" ||
            savedState?.gameState === "finished")
        ) {
          try {
            const stats = await participantApi.getMyStats(gameId);
            if (!cancelled && stats) setMyResult(stats);
          } catch (statsError) {
            console.warn("Could not refresh participant stats:", statsError);
          }
          return;
        }

        const deadlineMs = new Date(data.deadline).getTime();
        const serverTimeMs = new Date(data.server_time).getTime();
        const remainingSeconds =
          Number.isFinite(deadlineMs) && Number.isFinite(serverTimeMs)
            ? Math.max(0, (deadlineMs - serverTimeMs) / 1000)
            : 0;

        setCurrentQuestion(restoredQuestion);
        setQuestionNumber(data.question_number || 1);
        setTotalQuestions(data.total_questions || 1);
        setSelectedOptionId(null);
        setIsSubmitting(false);
        setMyResult(null);
        setRevealedData(null);

        if (data.is_revealed) {
          clearInterval(timerRef.current);
          setRevealedData(data.revealed_data || null);
          setAnswerLocked(true);
          setGameState("reveal");
          try {
            const stats = await participantApi.getMyStats(gameId);
            if (!cancelled && stats) setMyResult(stats);
          } catch (statsError) {
            console.warn("Could not restore participant results:", statsError);
          }
          return;
        }

        if (data.already_answered) {
          clearInterval(timerRef.current);

          // If this exact question has already been scored, restore its result.
          try {
            const stats = await participantApi.getMyStats(gameId);
            const resultQuestionId = stats?.last_result?.question_id;

            if (
              !cancelled &&
              resultQuestionId != null &&
              String(resultQuestionId) === String(restoredQuestion.id)
            ) {
              setMyResult(stats);
              setAnswerLocked(true);
              setRevealedData(data.revealed_data || null);
              setGameState("reveal");
              return;
            }
          } catch (statsError) {
            console.warn("Could not check the participant's latest result:", statsError);
          }

          setAnswerLocked(true);
          setGameState("answered");
          setTimeLeft(Math.ceil(remainingSeconds));
        } else {
          setAnswerLocked(false);
          setGameState("question");
          startCountdown(remainingSeconds);
        }
      } catch (questionError) {
        if (cancelled) return;

        console.info(
          "No active question endpoint response; checking saved state and participant stats.",
          questionError?.message || ""
        );

        // If the page was refreshed during reveal or after the game ended,
        // restore the backend's latest personal result.
        try {
          const stats = await participantApi.getMyStats(gameId);
          if (cancelled) return;

          if (stats) {
            setMyResult(stats);

            const resultQuestionId = stats.last_result?.question_id;
            const savedQuestionId = savedState?.currentQuestion?.id;
            const resultMatchesSavedQuestion =
              resultQuestionId != null &&
              savedQuestionId != null &&
              String(resultQuestionId) === String(savedQuestionId);

            if (savedState?.gameState === "finished") {
              setGameState("finished");
              clearInterval(timerRef.current);
            } else if (
              savedState?.gameState === "reveal" ||
              resultMatchesSavedQuestion ||
              (!savedState?.gameState && stats.last_result)
            ) {
              setGameState("reveal");
              setAnswerLocked(true);
              clearInterval(timerRef.current);
            } else if (
              savedState?.gameState === "answered" ||
              savedState?.gameState === "paused"
            ) {
              setGameState(savedState.gameState);
              setAnswerLocked(true);
              clearInterval(timerRef.current);
            }
          }
        } catch (statsError) {
          console.warn(
            "Could not restore participant stats:",
            statsError?.message || ""
          );

          // Keep the saved view (question, locked, reveal, etc.) rather than
          // resetting the participant to the lobby.
          if (savedState?.gameState && !cancelled) {
            setGameState(savedState.gameState);
          }
        }
      }
    };

    const ws = new QuizWebSocket({
      role: "participant",
      gameId,
      token,

      onOpen: () => {
        console.log("Participant WS connected.");
        restoreParticipantState();
      },

      onError: (err) => {
        console.warn("Participant WS error:", err);
      },

      onMessage: (event, data) => {
        if (event === "QUESTION_STARTED") {
          setGameState("question");
          setCurrentQuestion(data.question);
          setQuestionNumber(data.question_number);
          setTotalQuestions(data.total_questions);

          setSelectedOptionId(null);
          setAnswerLocked(false);
          setIsSubmitting(false);
          setMyResult(null);
          setLeaderboard([]);
          setRevealedData(null);

          startCountdown(data.time_limit || 15);
        } else if (event === "ANSWER_ACK") {
          setAnswerLocked(true);
          setIsSubmitting(false);
          setGameState("answered");
          clearInterval(timerRef.current);
        } else if (event === "ERROR") {
          // The server can reject an answer (for example, if the deadline has
          // passed or the question has just been revealed). Do not leave the
          // player stuck in the optimistic "answered" state in that case.
          setIsSubmitting(false);
          setSelectedOptionId(null);
          setAnswerLocked(false);
          setAnswerError(data?.detail || "Your answer could not be recorded. Please try again.");
        } else if (event === "GAME_PAUSED") {
          clearInterval(timerRef.current);

          setGameState((prev) =>
            prev === "question" ? "paused" : prev
          );
        } else if (event === "GAME_RESUMED") {
          if (data.remaining_seconds != null) {
            startCountdown(data.remaining_seconds);
          }

          setGameState((prev) =>
            prev === "paused" ? "question" : prev
          );
        } else if (event === "ANSWER_REVEALED") {
          setGameState("reveal");
          setAnswerLocked(true);
          setRevealedData(data);
          clearInterval(timerRef.current);

          // The backend sends this participant's personalized result as my_stats.
          if (data?.my_stats) {
            setMyResult(data.my_stats);
          } else {
            participantApi
              .getMyStats(gameId)
              .then((stats) => {
                setMyResult(stats);
              })
              .catch((e) =>
                console.warn("Failed to get my stats:", e)
              );
          }
        } else if (event === "PLAYER_PERSONAL_RESULT") {
          setMyResult(data?.my_stats || data);
        } else if (event === "LEADERBOARD_UPDATED") {
          setLeaderboard(data?.top || []);
        } else if (event === "PLAYER_KICKED") {
          setGameState("kicked");
          clearInterval(timerRef.current);
        } else if (event === "GAME_FINISHED") {
          setGameState("finished");
          clearInterval(timerRef.current);
          setLeaderboard(data?.leaderboard?.top || []);

          participantApi
            .getMyStats(gameId)
            .then((stats) => setMyResult(stats))
            .catch(() => {});
        }
      },
    });

    ws.connect();
    wsRef.current = ws;

    return () => {
      cancelled = true;
      clearInterval(timerRef.current);
      ws.close();
    };
  }, [gameId, token, startCountdown, savedState]);

  // Submit through REST so the player only sees a locked answer after the
  // backend confirms it. The participant WebSocket remains responsible for
  // live question and game-state events.
  const handleSelectOption = useCallback(
    async (optionId) => {
      if (
        answerLocked ||
        isSubmitting ||
        gameState !== "question" ||
        timeLeft <= 0
      ) {
        return;
      }

      setSelectedOptionId(optionId);
      setAnswerError("");
      setIsSubmitting(true);

      try {
        await participantApi.submitAnswer(gameId, {
          question_id: currentQuestion.id,
          option_id: optionId,
        });

        setAnswerLocked(true);
        setGameState("answered");
      } catch (err) {
        console.error("Answer submission failed:", err);
        setSelectedOptionId(null);
        setAnswerError(err.message || "Failed to lock in your answer.");
      } finally {
        setIsSubmitting(false);
      }
    },
    [
      answerLocked,
      isSubmitting,
      gameState,
      timeLeft,
      currentQuestion,
      gameId,
    ]
  );

  if (error) {
    return (
      <main className="quiz-background flex min-h-screen flex-col items-center justify-center p-6 text-center text-white">
        <h2 className="mb-4 text-2xl font-bold">Asteris</h2>

        <p className="mb-6 max-w-sm text-red-300">
          {error}
        </p>

        <button
          onClick={() => navigate("/")}
          className="rounded-xl bg-[#91F0DF] px-6 py-3 font-bold text-[#31064D]"
        >
          Join a Game
        </button>
      </main>
    );
  }

  return (
    <main className="quiz-background flex min-h-screen flex-col items-center justify-between p-4 text-white sm:p-6">
      {/* Top Header */}
      <header className="flex w-full max-w-md items-center justify-between border-b border-white/20 pb-4">
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold">{nickname}</span>
        </div>

        {myResult && (
          <div className="rounded-full bg-white/20 px-3 py-1 text-sm font-bold">
            {myResult.score || 0} pts
          </div>
        )}
      </header>

      {/* Main Game Card / State */}
      <div className="my-auto w-full max-w-md py-6">
        {/* Waiting Lobby */}
        {gameState === "lobby" && (
          <div className="rounded-3xl bg-white p-8 text-center text-[#31064D] shadow-2xl">
            <span className="text-5xl">🎮</span>

            <h2 className="brand-font mt-4 text-3xl font-bold">
              You're In!
            </h2>

            <p className="mt-2 text-gray-600">
              Welcome, <strong className="font-bold">{nickname}</strong>!
            </p>

            <div className="mt-6 rounded-2xl bg-[#31064D] p-6 text-center text-white">
              <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-4 border-white/30 border-t-[#91F0DF]" />

              <p className="text-lg font-bold">Waiting for host...</p>

              <p className="mt-1 text-xs text-purple-200">
                The quiz will begin as soon as the host starts.
              </p>
            </div>
          </div>
        )}

        {/* Active Question View */}
        {gameState === "question" && currentQuestion && (
          <div className="space-y-4">
            <div className="flex items-center justify-between text-sm font-bold">
              <span>
                Question {questionNumber} of {totalQuestions}
              </span>

              <span
                className={`rounded-full px-3 py-1 font-extrabold ${
                  timeLeft <= 5
                    ? "animate-pulse bg-red-500 text-white"
                    : "bg-white/20 text-[#91F0DF]"
                }`}
              >
                ⏱ {timeLeft}s
              </span>
            </div>

            <div className="rounded-3xl bg-white p-6 text-[#31064D] shadow-2xl">
              <h2 className="text-xl font-bold leading-snug">
                {currentQuestion.question_text}
              </h2>

              {/* IMAGE / AUDIO / VIDEO */}
              {currentQuestion.media_url && (
                <div className="mt-4 flex w-full justify-center">
                  {(() => {
                    const mediaType = String(
                      currentQuestion.media_type || "image"
                    ).toLowerCase();

                    const mediaUrl = getMediaUrl(
                      currentQuestion.media_url
                    );

                    if (mediaType === "image") {
                      return (
                        <img
                          src={mediaUrl}
                          alt="Question media"
                          className="max-h-48 w-full rounded-xl object-contain shadow"
                        />
                      );
                    }

                    if (mediaType === "audio") {
                      return (
                        <audio
                          controls
                          preload="metadata"
                          className="w-full"
                          src={mediaUrl}
                        >
                          Your browser does not support audio playback.
                        </audio>
                      );
                    }

                    if (mediaType === "video") {
                      return (
                        <video
                          controls
                          playsInline
                          preload="metadata"
                          className="max-h-64 w-full rounded-xl object-contain shadow"
                          src={mediaUrl}
                        >
                          Your browser does not support video playback.
                        </video>
                      );
                    }

                    return (
                      <p className="text-sm text-red-600">
                        Unsupported question media type: {mediaType}
                      </p>
                    );
                  })()}
                </div>
              )}
            </div>

            {/* Answer Options */}
            <div className="grid grid-cols-1 gap-3 pt-2 sm:grid-cols-2">
              {currentQuestion.options?.map((opt, idx) => {
                const scheme = optionColors[idx % optionColors.length];
                const isSelected = selectedOptionId === opt.id;

                return (
                  <button
                    key={opt.id}
                    type="button"
                    disabled={
                      isSubmitting ||
                      answerLocked ||
                      timeLeft <= 0
                    }
                    onClick={() => handleSelectOption(opt.id)}
                    className={`flex min-h-[80px] transform items-center gap-3 rounded-2xl p-4 text-left text-lg font-bold shadow-lg transition active:scale-95 ${scheme.card} ${scheme.text} ${
                      isSelected ? "ring-4 ring-white" : ""
                    }`}
                  >
                    <span
                      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl font-black ${scheme.letter}`}
                    >
                      {String.fromCharCode(65 + idx)}
                    </span>

                    <span className="flex-1 leading-tight">
                      {opt.option_text}
                    </span>
                  </button>
                );
              })}
            </div>
            {answerError && (
              <p role="alert" className="rounded-xl bg-red-950/70 px-4 py-3 text-sm font-semibold text-red-100">
                {answerError}
              </p>
            )}
          </div>
        )}

        {/* Paused View */}
        {gameState === "paused" && (
          <div className="rounded-3xl bg-white p-8 text-center text-[#31064D] shadow-2xl">
            <span className="text-5xl">⏸️</span>

            <h2 className="brand-font mt-4 text-3xl font-bold">
              Quiz Paused
            </h2>

            <p className="mt-3 text-gray-600">
              The host has paused the quiz. Please wait for the game to resume.
            </p>
          </div>
        )}

        {/* Answer Locked View */}
        {gameState === "answered" && (
          <div className="rounded-3xl bg-white p-8 text-center text-[#31064D] shadow-2xl">
            <span className="text-5xl">🔒</span>

            <h2 className="brand-font mt-4 text-3xl font-bold">
              Answer Locked In!
            </h2>

            <p className="mt-2 text-gray-600">
              Hold tight! Results will appear once time runs out or the host reveals the answer.
            </p>

            <div className="mt-6 flex items-center justify-center gap-2 text-sm font-semibold text-purple-700">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-purple-300 border-t-purple-700" />
              <span>Waiting for reveal...</span>
            </div>
          </div>
        )}

        {/* Reveal Results View */}
        {gameState === "reveal" && (
          <div className="rounded-3xl bg-white p-8 text-center text-[#31064D] shadow-2xl">
            <h2 className="brand-font text-3xl font-bold">
              Question Scored!
            </h2>

            {currentQuestion?.options?.length > 0 && revealedData?.correct_option_id != null && (
              <div className="mt-4 rounded-2xl bg-green-100 p-4 text-left text-green-900">
                <p className="text-xs font-bold uppercase tracking-wider">Correct answer</p>
                <p className="mt-1 text-lg font-extrabold">
                  {currentQuestion.options.find((option) => option.id === revealedData.correct_option_id)?.option_text || "Correct option revealed"}
                </p>
              </div>
            )}

            {myResult?.last_result ? (
              <div className="mt-4">
                {myResult.last_result.is_correct ? (
                  <div className="rounded-2xl bg-green-100 p-4 text-green-800">
                    <span className="text-4xl">🎉</span>

                    <p className="mt-2 text-xl font-bold">Correct!</p>

                    <p className="text-sm">
                      +{myResult.last_result.points || 0} points
                    </p>
                  </div>
                ) : (
                  <div className="rounded-2xl bg-red-100 p-4 text-red-800">
                    <span className="text-4xl">❌</span>

                    <p className="mt-2 text-xl font-bold">Incorrect</p>

                    <p className="text-sm">
                      Better luck on the next one!
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <p className="mt-4 text-gray-600">
                Waiting for next question from host...
              </p>
            )}

            {myResult && (
              <div className="mt-6 flex justify-around border-t pt-4">
                <div>
                  <p className="text-xs font-bold uppercase text-gray-500">
                    Total Score
                  </p>

                  <p className="text-2xl font-extrabold text-[#31064D]">
                    {myResult.score || 0}
                  </p>
                </div>

                <div>
                  <p className="text-xs font-bold uppercase text-gray-500">
                    Rank
                  </p>

                  <p className="text-2xl font-extrabold text-[#C51E50]">
                    #{myResult.rank ?? "-"}
                  </p>
                </div>

                <div>
                  <p className="text-xs font-bold uppercase text-gray-500">
                    Streak
                  </p>

                  <p className="text-2xl font-extrabold text-amber-500">
                    {myResult.streak || 0} 🔥
                  </p>
                </div>
              </div>
            )}

            {leaderboard.length > 0 && (
              <section className="mt-6 border-t pt-5 text-left">
                <h3 className="brand-font text-xl font-bold">Leaderboard</h3>
                <div className="mt-3 space-y-2">
                  {leaderboard.slice(0, 5).map((entry, index) => (
                    <div key={entry.participant_id} className="flex items-center justify-between rounded-xl bg-[#F0EAF7] px-4 py-3 text-sm font-semibold">
                      <span className="truncate"><strong className="mr-2">#{entry.rank || index + 1}</strong>{entry.nickname}</span>
                      <span className="ml-3 shrink-0 text-[#31064D]">{entry.score} pts</span>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        )}

        {/* Kicked View */}
        {gameState === "kicked" && (
          <div className="rounded-3xl bg-white p-8 text-center text-[#31064D] shadow-2xl">
            <span className="text-5xl">🚫</span>

            <h2 className="brand-font mt-4 text-2xl font-bold text-red-600">
              Removed from game
            </h2>

            <p className="mt-2 text-gray-600">
              The host has removed you from this quiz session.
            </p>

            <button
              onClick={() => navigate("/")}
              className="mt-6 rounded-xl bg-[#31064D] px-6 py-2.5 font-bold text-white"
            >
              Back to Home
            </button>
          </div>
        )}

        {/* Finished View */}
        {gameState === "finished" && (
          <div className="rounded-3xl bg-white p-8 text-center text-[#31064D] shadow-2xl">
            <span className="text-5xl">🏆</span>

            <h2 className="brand-font mt-4 text-3xl font-bold">
              Game Over!
            </h2>

            <p className="mt-2 text-gray-600">
              Thanks for playing, {nickname}!
            </p>

            {myResult && (
              <div className="my-6 rounded-2xl bg-[#EDE4F5] p-6 text-[#31064D]">
                <p className="text-xs font-bold uppercase tracking-widest text-[#6B5680]">
                  Your Final Standing
                </p>

                <p className="brand-font mt-2 text-5xl font-black text-[#C51E50]">
                  #{myResult.rank ?? "-"}
                </p>

                <p className="mt-1 text-xl font-bold">
                  {myResult.score || 0} points
                </p>
              </div>
            )}

            <button
              onClick={() => navigate("/")}
              className="rounded-xl bg-[#31064D] px-8 py-3.5 font-bold text-white transition hover:bg-[#49205C]"
            >
              PLAY AGAIN
            </button>
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="text-center text-xs text-purple-200/60">
        Asteris Live Quiz
      </footer>
    </main>
  );
}

export default QuestionScreen;
