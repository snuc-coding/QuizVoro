
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";

const LIVE_STATE_KEY = "asterisLiveQuizState";
const GAME_PIN_PREFIX = "asterisGamePin_";

function generateGamePin() {
  return String(Math.floor(10000000 + Math.random() * 90000000));
}

function getOrCreateGamePin(quizId) {
  const key = `${GAME_PIN_PREFIX}${quizId}`;
  let pin = localStorage.getItem(key);

  if (!/^\d{8}$/.test(pin || "")) {
    pin = generateGamePin();
    localStorage.setItem(key, pin);
  }

  return pin;
}

function getQuestionText(question) {
  return (
    question?.text ||
    question?.question ||
    question?.questionText ||
    "Untitled question"
  );
}

function HostDashboard({
  quiz,
  onOpenProjector,
  onBack,
  onStartQuiz,
}) {
  const navigate = useNavigate();
  const quizId = quiz?.id;

  const questions = Array.isArray(quiz?.questions)
    ? quiz.questions
    : [];

  const questionCount =
    questions.length ||
    Number(quiz?.questionCount) ||
    (typeof quiz?.questions === "number" ? quiz.questions : 0);

  const [gamePin, setGamePin] = useState("");
  const [liveState, setLiveState] = useState(null);
  const [notice, setNotice] = useState("");

  const status = liveState?.status || "ready";
  const currentIndex = liveState?.currentQuestionIndex || 0;
  const showLeaderboard = Boolean(liveState?.showLeaderboard);

  const isReady = status === "ready";
  const isRunning = status === "running";
  const isResults = status === "results";
  const isEnded = status === "ended";

  const isLastQuestion =
    questionCount > 0 && currentIndex >= questionCount - 1;

  const playerCount = Number(liveState?.totalPlayers || 0);

  const joinUrl =
    gamePin && !isEnded
      ? `${window.location.origin}/join?pin=${encodeURIComponent(gamePin)}`
      : "";

  // Load the selected quiz session.
  useEffect(() => {
    if (!quizId) return;

    const pin = getOrCreateGamePin(quizId);
    setGamePin(pin);

    try {
      const saved = JSON.parse(
        localStorage.getItem(LIVE_STATE_KEY) || "null"
      );

      const initialState =
        saved && String(saved.quizId) === String(quizId)
          ? { ...saved, gamePin: saved.gamePin || pin }
          : {
              quizId,
              gamePin: pin,
              status: "ready",
              currentQuestionIndex: 0,
              showLeaderboard: false,
              leaderboard: [],
              totalPlayers: 0,
              answeredCount: 0,
              updatedAt: Date.now(),
            };

      setLiveState(initialState);
      localStorage.setItem(
        LIVE_STATE_KEY,
        JSON.stringify(initialState)
      );
    } catch (error) {
      console.error("Unable to load quiz state:", error);
      setNotice("Unable to load the quiz session.");
    }
  }, [quizId]);

  // Synchronize state changes from the projector or another tab.
  useEffect(() => {
    function handleStorage(event) {
      if (event.key !== LIVE_STATE_KEY || !event.newValue) return;

      try {
        const nextState = JSON.parse(event.newValue);

        if (String(nextState.quizId) === String(quizId)) {
          setLiveState(nextState);

          if (/^\d{8}$/.test(nextState.gamePin || "")) {
            setGamePin(nextState.gamePin);
          }
        }
      } catch (error) {
        console.error("Unable to synchronize quiz state:", error);
      }
    }

    window.addEventListener("storage", handleStorage);

    return () => window.removeEventListener("storage", handleStorage);
  }, [quizId]);

  // Save state so the projector tab can react to host controls.
  function saveLiveState(updates) {
    if (!quizId || !liveState) return;

    const nextState = {
      ...liveState,
      ...updates,
      quizId,
      gamePin,
      updatedAt: Date.now(),
    };

    localStorage.setItem(
      LIVE_STATE_KEY,
      JSON.stringify(nextState)
    );

    setLiveState(nextState);
    setNotice("");
  }

  function handleStartQuiz() {
    if (!questionCount || !isReady) return;

    saveLiveState({
      status: "running",
      currentQuestionIndex: 0,
      showLeaderboard: false,
    });

    onStartQuiz?.();
  }

  function handleShowResults() {
    if (!isRunning) return;

    saveLiveState({
      status: "results",
      showLeaderboard: false,
    });
  }

  function handleNextQuestion() {
    if (!isResults || isLastQuestion) return;

    saveLiveState({
      status: "running",
      currentQuestionIndex: currentIndex + 1,
      showLeaderboard: false,
    });
  }

  function handleShowLeaderboard() {
    if (!isResults || isLastQuestion) return;

    saveLiveState({
      showLeaderboard: true,
    });
  }

  function handleReturnToResults() {
    if (!showLeaderboard || isEnded) return;

    saveLiveState({
      status: "results",
      showLeaderboard: false,
    });
  }

  function handleShowFinalLeaderboard() {
    if (!isResults || !isLastQuestion) return;

    saveLiveState({
      status: "ended",
      showLeaderboard: true,
    });
  }

  function handleEndQuiz() {
    if (isEnded) return;

    if (
      !window.confirm(
        "End this quiz and show the final leaderboard?"
      )
    ) {
      return;
    }

    saveLiveState({
      status: "ended",
      showLeaderboard: true,
    });
  }

  // Restart the session and notify the projector tab.
  function handleRestartQuiz() {
    if (
      !window.confirm(
        "Restart this quiz from Question 1? The current session scores will be reset."
      )
    ) {
      return;
    }

    const pin = gamePin || getOrCreateGamePin(quizId);

    const resetState = {
      quizId,
      gamePin: pin,
      status: "ready",
      currentQuestionIndex: 0,
      showLeaderboard: false,
      leaderboard: [],
      totalPlayers: 0,
      answeredCount: 0,
      updatedAt: Date.now(),
    };

    localStorage.setItem(
      LIVE_STATE_KEY,
      JSON.stringify(resetState)
    );

    setGamePin(pin);
    setLiveState(resetState);
    setNotice("Quiz reset. You can start again.");
  }

  function handleOpenProjector() {
    if (!quizId) return;

    sessionStorage.setItem(
      "asterisSelectedQuizId",
      String(quizId)
    );

    if (onOpenProjector) {
      onOpenProjector();
      return;
    }

    const projector = window.open(
      `/stage?quizId=${encodeURIComponent(quizId)}`,
      "asteris-projector"
    );

    if (!projector) {
      setNotice("Allow pop-ups in your browser to open the projector.");
    } else {
      projector.focus();
    }
  }

  async function handleCopyJoinLink() {
    if (isEnded || !joinUrl) return;

    try {
      await navigator.clipboard.writeText(joinUrl);
      setNotice("Join link copied successfully.");
    } catch {
      setNotice(`Copy this link manually: ${joinUrl}`);
    }
  }

  const stateLabel = isEnded
    ? "Quiz completed"
    : showLeaderboard
      ? "Leaderboard displayed"
      : isResults
        ? "Question results"
        : isRunning
          ? `Question ${currentIndex + 1} in progress`
          : "Ready to host";

  if (!quiz) {
    return (
      <main className="quiz-background flex min-h-screen items-center justify-center px-5 text-white">
        <div className="rounded-2xl border border-white/15 bg-[#260638] p-8 text-center">
          <h1 className="brand-font text-3xl">Asteris</h1>
          <p className="mt-3 text-purple-100">
            Loading quiz details...
          </p>
          <button
            type="button"
            onClick={onBack}
            className="mt-5 rounded-xl border border-white/30 px-5 py-3"
          >
            Back to quiz list
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="quiz-background min-h-screen px-4 py-6 text-white sm:px-8 lg:px-10">
      <div className="mx-auto max-w-[1500px]">

        {/* Header */}
        <header className="mb-7 flex items-center justify-between gap-4 border-b border-white/15 pb-5">
          <button
            type="button"
            onClick={() => navigate("/admin/dashboard")}
            className="brand-font text-3xl font-bold sm:text-4xl"
          >
            Asteris
          </button>

          <button
            type="button"
            onClick={() => navigate("/admin/dashboard")}
            className="rounded-xl border border-white/30 px-4 py-3 text-sm font-bold transition hover:bg-white/10 sm:px-6"
          >
            ADMIN DASHBOARD
          </button>
        </header>

        {/* Quiz heading */}
        <section className="mb-5">
          <p className="nav-font text-xs font-bold tracking-[0.28em] text-[#91F0DF]">
            LIVE QUIZ HOSTING
          </p>

          <div className="mt-2 flex flex-wrap items-center gap-3">
            <h1 className="brand-font text-4xl font-bold sm:text-5xl">
              {quiz.name || quiz.title || "Your Quiz"}
            </h1>

            <span className="rounded-full border border-white/20 bg-white/10 px-4 py-2 text-sm">
              {questionCount} {questionCount === 1 ? "question" : "questions"}
            </span>
          </div>

          <p className="mt-3 flex items-center gap-2 text-sm text-purple-100">
            <span className="h-2.5 w-2.5 rounded-full bg-[#91F0DF]" />
            {stateLabel}
          </p>

          <p className="mt-2 max-w-3xl text-sm leading-6 text-purple-100/80">
            {isEnded
              ? "This quiz has finished. The final leaderboard is selected for the projector."
              : "Manage the live quiz, show results, and choose what appears on the projector after each question."}
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
                {isEnded
                  ? "Quiz completed"
                  : showLeaderboard
                    ? "Leaderboard is displayed"
                    : isResults
                      ? "Choose what happens next"
                      : isRunning
                        ? `Question ${currentIndex + 1} is live`
                        : "Ready to launch?"}
              </h2>

              <p className="mt-2 text-sm leading-6 text-purple-100/75">
                {isEnded
                  ? "Restart the quiz whenever you are ready for a new session."
                  : showLeaderboard
                    ? "Return to the results controls or continue managing the quiz."
                    : isResults
                      ? isLastQuestion
                        ? "This is the final question. Display the final leaderboard to finish."
                        : "Choose whether to continue to the next question or show the leaderboard."
                      : isRunning
                        ? "Show the question results when you are ready."
                        : "Start the quiz when you are ready."}
              </p>
            </div>

            {liveState && !isReady && (
              <div className="rounded-xl border border-white/10 bg-white/10 px-5 py-3 text-center">
                <p className="text-xs tracking-wider text-purple-200">
                  PROGRESS
                </p>
                <p className="mt-1 text-2xl font-bold">
                  {Math.min(currentIndex + 1, questionCount)}
                  <span className="text-base font-normal text-purple-200">
                    {" "}/ {questionCount}
                  </span>
                </p>
              </div>
            )}
          </div>

          <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">

            {isReady && (
              <button
                type="button"
                onClick={handleStartQuiz}
                disabled={!questionCount}
                className="min-h-[58px] rounded-xl bg-[#91F0DF] px-4 py-4 font-extrabold text-[#21052F] transition hover:bg-[#ACF7EA] disabled:cursor-not-allowed disabled:opacity-50"
              >
                ▶ START QUIZ
              </button>
            )}

            {isRunning && (
              <button
                type="button"
                onClick={handleShowResults}
                className="min-h-[58px] rounded-xl bg-[#C51E50] px-4 py-4 font-extrabold text-white transition hover:bg-[#D92D62]"
              >
                SHOW QUESTION RESULTS
              </button>
            )}

            {isResults && !isLastQuestion && (
              <>
                <button
                  type="button"
                  onClick={handleNextQuestion}
                  className="min-h-[58px] rounded-xl bg-[#91F0DF] px-4 py-4 font-extrabold text-[#21052F] transition hover:bg-[#ACF7EA]"
                >
                  NEXT QUESTION →
                </button>

                <button
                  type="button"
                  onClick={handleShowLeaderboard}
                  className="min-h-[58px] rounded-xl bg-white px-4 py-4 font-extrabold text-[#31064D] transition hover:bg-purple-100"
                >
                  🏆 SHOW LEADERBOARD
                </button>
              </>
            )}

            {isResults && isLastQuestion && (
              <button
                type="button"
                onClick={handleShowFinalLeaderboard}
                className="min-h-[58px] rounded-xl bg-[#91F0DF] px-4 py-4 font-extrabold text-[#21052F] transition hover:bg-[#ACF7EA]"
              >
                🏆 SHOW FINAL LEADERBOARD
              </button>
            )}

            {showLeaderboard && !isEnded && !isLastQuestion && (
              <button
                type="button"
                onClick={handleReturnToResults}
                className="min-h-[58px] rounded-xl border border-white/40 px-4 py-4 font-bold transition hover:bg-white/10"
              >
                RETURN TO RESULTS
              </button>
            )}

            {!isEnded && (
              <>
                <button
                  type="button"
                  onClick={handleOpenProjector}
                  className="min-h-[58px] rounded-xl border border-white/30 px-4 py-4 font-bold transition hover:bg-white/10"
                >
                  OPEN PROJECTOR ↗
                </button>

                <button
                  type="button"
                  onClick={handleEndQuiz}
                  className="min-h-[58px] rounded-xl border border-rose-300/70 px-4 py-4 font-bold text-rose-100 transition hover:bg-rose-500/15"
                >
                  END QUIZ
                </button>
              </>
            )}

            {isEnded && (
              <button
                type="button"
                onClick={handleRestartQuiz}
                className="min-h-[58px] rounded-xl bg-[#91F0DF] px-5 py-4 font-extrabold text-[#21052F] transition hover:bg-[#ACF7EA]"
              >
                ↻ RESTART QUIZ
              </button>
            )}
          </div>

          {isEnded && (
            <p className="mt-5 rounded-xl border border-[#91F0DF]/20 bg-white/5 p-4 text-sm text-purple-100">
              The quiz has ended. The joining card is hidden. Restart to begin a new session.
            </p>
          )}

          {notice && (
            <p className="mt-4 break-words rounded-lg border border-white/10 bg-white/10 p-3 text-sm text-purple-50">
              {notice}
            </p>
          )}
        </section>

        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_350px]">

          {/* Main column */}
          <div className="min-w-0">

            {/* Joining card disappears after completion */}
            {!isEnded && (
              <>
                <section className="grid gap-6 rounded-2xl bg-white p-5 text-[#31064D] shadow-xl sm:p-7 md:grid-cols-[minmax(0,1fr)_150px_minmax(0,1fr)]">

                  <div>
                    <p className="nav-font text-xs font-bold tracking-widest text-purple-700">
                      PLAYERS JOIN HERE
                    </p>

                    <h2 className="brand-font mt-2 text-3xl">
                      Game PIN
                    </h2>

                    <div className="mt-4 rounded-xl bg-[#F0EAF7] px-3 py-5 text-center">
                      <p className="whitespace-nowrap text-3xl font-black tracking-widest sm:text-4xl">
                        {gamePin
                          ? `${gamePin.slice(0, 3)} ${gamePin.slice(3)}`
                          : "--------"}
                      </p>
                    </div>
                  </div>

                  <div className="flex flex-col items-center justify-center border-t border-gray-200 pt-5 md:border-l md:border-t-0 md:pl-5 md:pt-0">
                    {joinUrl && (
                      <div className="rounded-xl border border-gray-200 p-2">
                        <QRCodeSVG
                          value={joinUrl}
                          size={112}
                          level="H"
                          includeMargin
                        />
                      </div>
                    )}

                    <p className="mt-2 text-sm text-gray-600">
                      Scan to join
                    </p>
                  </div>

                  <div className="flex flex-col justify-center border-t border-gray-200 pt-5 md:border-l md:pl-5 md:pt-0">
                    <h3 className="font-bold">Projector view</h3>

                    <p className="mt-2 text-sm leading-5 text-gray-600">
                      Open a separate audience screen for the live question,
                      results, and leaderboard.
                    </p>

                    <button
                      type="button"
                      onClick={handleOpenProjector}
                      className="nav-font mt-4 rounded-xl bg-[#31064D] px-4 py-3 font-bold text-white transition hover:bg-[#49205C]"
                    >
                      OPEN PROJECTOR VIEW ↗
                    </button>

                    <button
                      type="button"
                      onClick={handleCopyJoinLink}
                      className="mt-3 rounded-xl border border-purple-200 px-4 py-3 font-bold transition hover:bg-purple-50"
                    >
                      COPY JOIN LINK
                    </button>
                  </div>
                </section>

                <div className="mt-4 rounded-xl border border-white/10 bg-white/10 p-4 text-sm text-purple-100">
                  Players join on their phones. Questions and leaderboard changes are controlled by the host.
                </div>
              </>
            )}

            {/* Question sequence */}
            <section className="mt-6 rounded-2xl bg-white p-5 text-[#31064D] shadow-xl sm:p-7">
              <div className="flex items-center justify-between gap-3">
                <h2 className="brand-font text-2xl">
                  Question sequence
                </h2>

                <span className="text-sm text-gray-500">
                  {questionCount} questions
                </span>
              </div>

              {questions.map((question, index) => {
                const isCurrent =
                  index === currentIndex && !isEnded;

                const isCompleted =
                  isEnded || index < currentIndex;

                return (
                  <div
                    key={question.id ?? index}
                    className={`mt-4 flex items-center gap-3 rounded-xl border p-4 sm:gap-4 ${
                      isCurrent
                        ? "border-purple-300 bg-purple-50"
                        : "border-gray-200 bg-white"
                    }`}
                  >
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#F0DDFB] font-bold">
                      {index + 1}
                    </span>

                    <div className="min-w-0 flex-1">
                      <p className="break-words font-semibold">
                        {getQuestionText(question)}
                      </p>

                      <p className="mt-1 text-sm text-gray-500">
                        Multiple choice
                      </p>
                    </div>

                    <span className="shrink-0 rounded-full bg-gray-100 px-2 py-1 text-xs text-gray-600 sm:px-3">
                      {isCompleted
                        ? "Completed"
                        : isCurrent && isResults
                          ? "Results"
                          : isCurrent && isRunning
                            ? "In progress"
                            : "Not started"}
                    </span>
                  </div>
                );
              })}

              {questions.length === 0 && (
                <p className="mt-4 rounded-xl bg-purple-50 p-4 text-sm text-gray-600">
                  Question details are unavailable for this quiz.
                </p>
              )}
            </section>

            <button
              type="button"
              onClick={onBack}
              className="nav-font mt-5 w-full rounded-xl border border-white/20 bg-white/5 px-5 py-3 font-bold transition hover:bg-white/10"
            >
              ← BACK TO QUIZ LIST
            </button>
          </div>

          {/* Right column */}
          <aside className="space-y-5">

            <section className="rounded-2xl border border-white/10 bg-[#260638]/85 p-6 shadow-xl">
              <h2 className="brand-font text-2xl">
                Live status
              </h2>

              <div className="mt-4 flex items-center justify-between gap-3 rounded-xl bg-white p-4 text-[#31064D]">
                <div>
                  <p className="text-sm text-gray-500">
                    Players joined
                  </p>
                  <p className="mt-1 text-3xl font-bold">
                    {playerCount}
                  </p>
                </div>

                <span className="rounded-full bg-[#F0EAF7] px-3 py-1 text-xs">
                  {isEnded
                    ? "Finished"
                    : showLeaderboard
                      ? "Leaderboard"
                      : isResults
                        ? "Results"
                        : isRunning
                          ? "In progress"
                          : "Waiting to start"}
                </span>
              </div>

              <p className="mt-3 text-xs leading-5 text-purple-100/60">
                The player count updates when the joining system supplies the live total.
              </p>
            </section>

            <section className="rounded-2xl border border-white/10 bg-[#260638]/85 p-6 shadow-xl">
              <h2 className="brand-font text-xl">
                Quiz settings
              </h2>

              <div className="mt-4 space-y-3 text-sm">
                <div className="flex justify-between gap-3">
                  <span className="text-purple-100/70">
                    Quiz name
                  </span>
                  <span className="text-right">
                    {quiz.name || quiz.title || "Quiz"}
                  </span>
                </div>

                <div className="flex justify-between gap-3">
                  <span className="text-purple-100/70">
                    Total questions
                  </span>
                  <span>{questionCount}</span>
                </div>

                <div className="flex justify-between gap-3">
                  <span className="text-purple-100/70">
                    Question type
                  </span>
                  <span>Multiple choice</span>
                </div>

                <div className="flex justify-between gap-3">
                  <span className="text-purple-100/70">
                    Results after each question
                  </span>
                  <span>Yes</span>
                </div>
              </div>
            </section>
          </aside>
        </div>
      </div>
    </main>
  );
}

export default HostDashboard;
