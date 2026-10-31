
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

const LIVE_STATE_KEY = "asterisLiveQuizState";
const QUIZZES_KEY = "asterisQuizzes";

function PresentationControlPage() {
  const navigate = useNavigate();

  const [quiz, setQuiz] = useState(null);
  const [error, setError] = useState("");
  const [liveState, setLiveState] = useState(null);

  useEffect(() => {
    try {
      const selectedQuizId = sessionStorage.getItem(
        "asterisSelectedQuizId"
      );

      const savedQuizzes = JSON.parse(
        localStorage.getItem(QUIZZES_KEY) || "[]"
      );

      const selectedQuiz = Array.isArray(savedQuizzes)
        ? savedQuizzes.find(
            (item) => String(item.id) === String(selectedQuizId)
          )
        : null;

      if (!selectedQuiz) {
        setError("The selected quiz could not be found.");
        return;
      }

      if (
        !Array.isArray(selectedQuiz.questions) ||
        selectedQuiz.questions.length === 0
      ) {
        setError("This quiz does not contain any questions.");
        return;
      }

      setQuiz(selectedQuiz);

      const savedState = JSON.parse(
        localStorage.getItem(LIVE_STATE_KEY) || "null"
      );

      if (
        savedState &&
        String(savedState.quizId) === String(selectedQuiz.id) &&
        savedState.status !== "ended"
      ) {
        setLiveState(savedState);
      } else {
        const initialState = {
          quizId: selectedQuiz.id,
          status: "ready",
          currentQuestionIndex: 0,
          showLeaderboard: false,
          leaderboard: [],
          updatedAt: Date.now(),
        };

        setLiveState(initialState);
        localStorage.setItem(
          LIVE_STATE_KEY,
          JSON.stringify(initialState)
        );
      }
    } catch (err) {
      console.error("Could not initialize live quiz:", err);
      setError("Unable to load the selected quiz.");
    }
  }, []);

  function saveLiveState(updates) {
    if (!quiz || !liveState) return;

    const nextState = {
      ...liveState,
      ...updates,
      quizId: quiz.id,
      updatedAt: Date.now(),
    };

    localStorage.setItem(
      LIVE_STATE_KEY,
      JSON.stringify(nextState)
    );

    setLiveState(nextState);
    setError("");
  }

  function handleOpenProjector() {
    if (!quiz?.id) {
      setError("Please select a valid quiz first.");
      return;
    }

    const savedPin = localStorage.getItem(
      `asterisGamePin_${quiz.id}`
    );

    const readyState = {
      ...liveState,
      quizId: quiz.id,
      gamePin: savedPin || undefined,
      status: "ready",
      currentQuestionIndex: 0,
      showLeaderboard: false,
      updatedAt: Date.now(),
    };

    localStorage.setItem(
      LIVE_STATE_KEY,
      JSON.stringify(readyState)
    );

    setLiveState(readyState);

    const projectorUrl =
      `/stage?quizId=${encodeURIComponent(quiz.id)}`;

    const projectorWindow = window.open(
      projectorUrl,
      "asterisProjector"
    );

    if (!projectorWindow) {
      setError(
        "Projector popup blocked. Allow pop-ups for this site and try again."
      );
      return;
    }

    projectorWindow.focus();
  }

  function handleStartQuiz() {
    if (!quiz?.questions?.length) return;

    saveLiveState({
      status: "running",
      currentQuestionIndex: 0,
      showLeaderboard: false,
    });
  }

  // Finish the current question and show its results.
  // This also applies to the final question.
  function handleShowResults() {
    if (!liveState || liveState.status !== "running") return;

    saveLiveState({
      status: "results",
      showLeaderboard: false,
    });
  }

  function handleNextQuestion() {
    if (
      !quiz ||
      !liveState ||
      liveState.status !== "results"
    ) {
      return;
    }

    const nextIndex = liveState.currentQuestionIndex + 1;

    if (nextIndex >= quiz.questions.length) return;

    saveLiveState({
      status: "running",
      currentQuestionIndex: nextIndex,
      showLeaderboard: false,
    });
  }

  function handleShowLeaderboard() {
    if (!liveState || liveState.status === "ended") return;

    saveLiveState({
      showLeaderboard: true,
    });
  }

  function handleHideLeaderboard() {
    if (!liveState || liveState.status === "ended") return;

    saveLiveState({
      showLeaderboard: false,
    });
  }

  function handleEndQuiz() {
    if (
      !window.confirm(
        "End this quiz now and show the final leaderboard?"
      )
    ) {
      return;
    }

    saveLiveState({
      status: "ended",
      showLeaderboard: true,
    });
  }

  function handleLogout() {
    sessionStorage.removeItem("asterisAdminLoggedIn");
    sessionStorage.removeItem("asterisAdminUsername");
    sessionStorage.removeItem("asterisSelectedQuizId");

    navigate("/", { replace: true });
  }

  const questionIndex = liveState?.currentQuestionIndex ?? 0;
  const currentQuestion = quiz?.questions?.[questionIndex];
  const status = liveState?.status;

  const isRunning = status === "running";
  const isResults = status === "results";
  const isEnded = status === "ended";
  const isReady = status === "ready";

  const isLastQuestion =
    Boolean(quiz) &&
    questionIndex >= quiz.questions.length - 1;

  // Use only scores supplied by the live state.
  const leaderboard = Array.isArray(liveState?.leaderboard)
    ? [...liveState.leaderboard]
        .filter((player) => player != null)
        .sort(
          (a, b) =>
            Number(b.score || 0) - Number(a.score || 0)
        )
        .slice(0, 10)
    : [];

  const answeredCount =
    liveState?.answeredCount != null &&
    Number.isFinite(Number(liveState.answeredCount))
      ? Number(liveState.answeredCount)
      : null;

  const totalPlayers =
    liveState?.totalPlayers != null &&
    Number.isFinite(Number(liveState.totalPlayers))
      ? Number(liveState.totalPlayers)
      : null;

  const hasAnswerStats =
    answeredCount !== null &&
    totalPlayers !== null &&
    totalPlayers > 0;

  const responseRate = hasAnswerStats
    ? Math.max(
        0,
        Math.min(
          100,
          Math.round((answeredCount / totalPlayers) * 100)
        )
      )
    : null;

  return (
    <main className="min-h-screen px-4 py-8 text-white sm:px-8 lg:px-12">
      <div className="mx-auto w-full max-w-6xl">
        <header className="mb-8 flex items-center justify-between gap-4 border-b border-white/20 pb-6">
          <button
            type="button"
            onClick={() => navigate("/admin/dashboard")}
            className="brand-font text-4xl font-bold sm:text-5xl"
          >
            Quizvoro
          </button>

          <button
            type="button"
            onClick={handleLogout}
            className="rounded-xl border border-white/40 px-5 py-3 font-bold hover:bg-white/10"
          >
            LOGOUT
          </button>
        </header>

        <p className="mb-3 text-sm font-bold uppercase tracking-[0.25em] text-[#91F0DF]">
          LIVE QUIZ CONTROL
        </p>

        <h1 className="brand-font text-4xl font-bold sm:text-5xl">
          {quiz?.title || quiz?.name || "Presentation setup"}
        </h1>

        <p className="mt-3 text-white/80">
          Control the projector and manage each question.
        </p>

        {error && (
          <section className="mt-6 rounded-xl bg-white p-5 text-red-700">
            <p role="alert">{error}</p>
          </section>
        )}

        {!quiz && !error && (
          <p className="mt-8">Loading selected quiz...</p>
        )}

        {quiz && liveState && (
          <>
            <section className="mt-8 rounded-2xl bg-white p-6 text-[#31064D] shadow-xl sm:p-8">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-bold uppercase tracking-wider text-[#C51E50]">
                    {isReady
                      ? "READY TO START"
                      : isRunning
                        ? "QUESTION IN PROGRESS"
                        : isResults
                          ? "QUESTION RESULTS"
                          : "QUIZ COMPLETED"}
                  </p>

                  <h2 className="mt-2 text-2xl font-bold">
                    {isEnded
                      ? "Quiz completed"
                      : `Question ${questionIndex + 1} of ${quiz.questions.length}`}
                  </h2>
                </div>

                <span className="rounded-full bg-purple-100 px-4 py-2 text-sm font-bold">
                  {quiz.questions.length} questions
                </span>
              </div>

              {currentQuestion && !isEnded && (
                <div className="mt-6 rounded-xl border border-gray-200 p-5">
                  <p className="text-sm font-bold uppercase tracking-wider text-gray-500">
                    Current question
                  </p>

                  <p className="mt-3 text-lg font-semibold">
                    {currentQuestion.text ||
                      currentQuestion.question ||
                      currentQuestion.questionText}
                  </p>

                  <div className="mt-4 grid gap-2 sm:grid-cols-2">
                    {(Array.isArray(currentQuestion.options)
                      ? currentQuestion.options
                      : []
                    ).map((option, index) => {
                      const optionText =
                        typeof option === "string"
                          ? option
                          : option?.text || option?.label || "";

                      return (
                        <div
                          key={`${index}-${optionText}`}
                          className="rounded-lg bg-gray-100 p-3"
                        >
                          <span className="mr-2 font-bold">
                            {String.fromCharCode(65 + index)}.
                          </span>
                          {optionText}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Question response statistics */}
              {isResults && (
                <section className="mt-6 rounded-xl border border-purple-200 bg-purple-50 p-5">
                  <h3 className="text-xl font-bold">
                    Question results
                  </h3>

                  {hasAnswerStats ? (
                    <>
                      <p className="mt-3 text-3xl font-black">
                        {answeredCount}/{totalPlayers}
                      </p>

                      <p className="mt-1">
                        Players answered · {responseRate}% response rate
                      </p>

                      <div className="mt-4 h-3 overflow-hidden rounded-full bg-purple-200">
                        <div
                          className="h-full rounded-full bg-emerald-600"
                          style={{ width: `${responseRate}%` }}
                        />
                      </div>
                    </>
                  ) : (
                    <p className="mt-3 text-gray-600">
                      Answer statistics are not available yet.
                      They must be supplied by the player system
                      or backend.
                    </p>
                  )}

                  {isLastQuestion && (
                    <p className="mt-4 font-semibold">
                      This was the final question. Show the
                      leaderboard or end the quiz.
                    </p>
                  )}
                </section>
              )}

              {/* Host controls */}
              <div className="mt-6 grid gap-3 sm:grid-cols-2">
                <button
                  type="button"
                  onClick={handleOpenProjector}
                  className="rounded-xl border border-[#31064D] px-5 py-4 font-bold hover:bg-purple-50"
                >
                  OPEN PROJECTOR VIEW ↗
                </button>

                {isReady && (
                  <button
                    type="button"
                    onClick={handleStartQuiz}
                    className="rounded-xl bg-[#C51E50] px-5 py-4 font-bold text-white hover:bg-[#D6295D]"
                  >
                    START QUIZ
                  </button>
                )}

                {isRunning && (
                  <button
                    type="button"
                    onClick={handleShowResults}
                    className="rounded-xl bg-[#C51E50] px-5 py-4 font-bold text-white hover:bg-[#D6295D]"
                  >
                    SHOW QUESTION RESULTS
                  </button>
                )}

                {isResults && !isLastQuestion && (
                  <button
                    type="button"
                    onClick={handleNextQuestion}
                    className="rounded-xl bg-[#91F0DF] px-5 py-4 font-bold text-[#21052F] hover:bg-[#ACF7EA]"
                  >
                    NEXT QUESTION →
                  </button>
                )}

                {isResults && (
                  <button
                    type="button"
                    onClick={handleShowLeaderboard}
                    className="rounded-xl bg-[#91F0DF] px-5 py-4 font-bold text-[#21052F] hover:bg-[#ACF7EA]"
                  >
                    SHOW LEADERBOARD
                  </button>
                )}

                {liveState.showLeaderboard && !isEnded && (
                  <button
                    type="button"
                    onClick={handleHideLeaderboard}
                    className="rounded-xl border border-[#31064D] px-5 py-4 font-bold hover:bg-purple-50"
                  >
                    RETURN TO QUIZ
                  </button>
                )}

                {!isEnded && (
                  <button
                    type="button"
                    onClick={handleEndQuiz}
                    className="rounded-xl border border-red-300 px-5 py-4 font-bold text-red-700 hover:bg-red-50"
                  >
                    END QUIZ
                  </button>
                )}
              </div>

              {/* Real leaderboard only; never display invented scores */}
              {liveState.showLeaderboard && (
                <section className="mt-8 border-t border-gray-200 pt-6">
                  <h3 className="text-2xl font-bold">
                    {isEnded ? "Final Top 10" : "Leaderboard"}
                  </h3>

                  {leaderboard.length > 0 ? (
                    <div className="mt-4 space-y-2">
                      {leaderboard.map((player, index) => (
                        <div
                          key={player.id ?? player.name ?? player.nickname ?? index}
                          className={`flex items-center justify-between gap-3 rounded-xl p-4 ${
                            index === 0
                              ? "bg-amber-100"
                              : index === 1
                                ? "bg-gray-200"
                                : index === 2
                                  ? "bg-orange-100"
                                  : "bg-gray-100"
                          }`}
                        >
                          <span className="font-semibold">
                            {index < 3
                              ? ["🥇", "🥈", "🥉"][index]
                              : `#${index + 1}`}{" "}
                            {player.name || player.nickname || "Player"}
                          </span>

                          <span className="whitespace-nowrap font-bold">
                            {Number(player.score || 0).toLocaleString()} points
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-4 rounded-xl bg-gray-100 p-5 text-gray-600">
                      No player scores are available yet. The
                      leaderboard will populate when actual scores
                      are supplied by the player system or backend.
                    </p>
                  )}
                </section>
              )}

              {isEnded && (
                <p className="mt-6 rounded-xl bg-green-100 p-4 text-sm font-semibold text-green-900">
                  Quiz finished. The final leaderboard is selected
                  for the projector.
                </p>
              )}
            </section>

            <button
              type="button"
              onClick={() => navigate("/admin/quizzes")}
              className="mt-6 w-full rounded-xl border border-white/40 bg-white/10 px-5 py-4 font-bold hover:bg-white/20"
            >
              CHANGE QUIZ
            </button>
          </>
        )}
      </div>
    </main>
  );
}

export default PresentationControlPage;
