
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

const LIVE_STATE_KEY = "asterisLiveQuizState";

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
        localStorage.getItem("asterisQuizzes") || "[]"
      );

      const selectedQuiz = Array.isArray(savedQuizzes)
        ? savedQuizzes.find(
            (item) => String(item.id) === selectedQuizId
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

      // Reuse the session only if it belongs to this quiz
      // and has not already ended.
      if (
        savedState &&
        String(savedState.quizId) === String(selectedQuiz.id) &&
        savedState.status !== "ended"
      ) {
        setLiveState(savedState);
      } else {
        setLiveState({
          quizId: selectedQuiz.id,
          status: "ready",
          currentQuestionIndex: 0,
          showLeaderboard: false,
          updatedAt: Date.now(),
        });
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

    localStorage.setItem(LIVE_STATE_KEY, JSON.stringify(nextState));
    setLiveState(nextState);
  }

  function handleStartQuiz() {
    if (!quiz?.questions?.length) return;

    saveLiveState({
      status: "running",
      currentQuestionIndex: 0,
      showLeaderboard: false,
    });
  }

  function handleNextQuestion() {
    if (!quiz || !liveState || liveState.status !== "running") return;

    const nextIndex = liveState.currentQuestionIndex + 1;

    if (nextIndex >= quiz.questions.length) {
      saveLiveState({
        status: "ended",
        showLeaderboard: true,
      });
      return;
    }

    saveLiveState({
      currentQuestionIndex: nextIndex,
      showLeaderboard: false,
    });
  }

  function handleToggleLeaderboard() {
    if (!liveState || liveState.status === "ended") return;

    saveLiveState({
      showLeaderboard: !liveState.showLeaderboard,
    });
  }

  function handleEndQuiz() {
    if (
      !window.confirm(
        "End this quiz now? The projector will show the finished state."
      )
    ) {
      return;
    }

    saveLiveState({
      status: "ended",
      showLeaderboard: true,
    });
  }

  

function handleOpenProjector() {
  if (!quiz?.id) {
    setError("Please select a valid quiz first.");
    return;
  }

  // Prepare a fresh waiting lobby before opening the projector.
  const readyState = {
    quizId: quiz.id,
    status: "ready",
    currentQuestionIndex: 0,
    showLeaderboard: false,
    updatedAt: Date.now(),
  };

  // Save the state so the projector reads "ready", not an old status.
  localStorage.setItem(
    "asterisLiveQuizState",
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
  setError("");
}

  function handleLogout() {
    sessionStorage.removeItem("asterisAdminLoggedIn");
    sessionStorage.removeItem("asterisAdminUsername");
    sessionStorage.removeItem("asterisSelectedQuizId");
    navigate("/", { replace: true });
  }

  const questionIndex = liveState?.currentQuestionIndex ?? 0;
  const currentQuestion = quiz?.questions?.[questionIndex];
  const isRunning = liveState?.status === "running";
  const isEnded = liveState?.status === "ended";

  // Demonstration scores only. Replace with actual scores later.
  const demoLeaderboard = [
    { name: "Participant 1", score: 300 },
    { name: "Participant 2", score: 200 },
    { name: "Participant 3", score: 100 },
  ];

  return (
    <main className="min-h-screen px-4 py-8 text-white sm:px-8 lg:px-12">
      <div className="mx-auto w-full max-w-5xl">
        <header className="mb-10 flex items-center justify-between gap-4 border-b border-white/20 pb-6">
          <button
            type="button"
            onClick={() => navigate("/admin/dashboard")}
            className="brand-font text-4xl font-bold sm:text-5xl"
          >
            Asteris
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
          {quiz?.title || "Presentation setup"}
        </h1>
        <p className="mt-4 text-white/80">
          Control the question displayed on the projector.
        </p>

        {error && (
          <section className="mt-6 rounded-xl bg-white p-6 text-red-700">
            <p role="alert">{error}</p>
            <button
              type="button"
              onClick={() => navigate("/admin/quizzes")}
              className="mt-4 rounded-lg bg-[#31064D] px-5 py-3 font-bold text-white"
            >
              BACK TO SAVED QUIZZES
            </button>
          </section>
        )}

        {quiz && liveState && !error && (
          <>
            <section className="mt-8 rounded-2xl bg-white p-6 text-[#31064D] shadow-xl sm:p-8">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-bold uppercase tracking-wider text-[#C51E50]">
                    {isEnded
                      ? "QUIZ ENDED"
                      : isRunning
                        ? "QUIZ IN PROGRESS"
                        : "READY TO START"}
                  </p>
                  <h2 className="mt-2 text-2xl font-bold">
                    {isEnded
                      ? "Quiz completed"
                      : `Question ${questionIndex + 1} of ${quiz.questions.length}`}
                  </h2>
                </div>
                <span className="rounded-full bg-purple-100 px-4 py-2 text-sm font-bold text-[#31064D]">
                  {quiz.questions.length} questions
                </span>
              </div>

              {currentQuestion && !isEnded && (
                <div className="mt-6 rounded-xl border border-gray-200 p-5">
                  <p className="text-sm font-bold uppercase tracking-wider text-gray-500">
                    Current question
                  </p>
                  <p className="mt-3 text-lg font-semibold">
                    {currentQuestion.text}
                  </p>
                  <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
                    {(currentQuestion.options || []).map((option, index) => (
                      <div
                        key={`${index}-${option}`}
                        className="rounded-lg bg-gray-100 p-3"
                      >
                        <span className="mr-2 font-bold">
                          {String.fromCharCode(65 + index)}.
                        </span>
                        {option}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
                <button
                  type="button"
                  onClick={handleOpenProjector}
                  className="rounded-xl border border-[#31064D] px-5 py-4 font-bold hover:bg-purple-50"
                >
                  OPEN PROJECTOR
                </button>

                {!isRunning && !isEnded && (
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
                    onClick={handleNextQuestion}
                    className="rounded-xl bg-[#C51E50] px-5 py-4 font-bold text-white hover:bg-[#D6295D]"
                  >
                    {questionIndex === quiz.questions.length - 1
                      ? "FINISH QUIZ"
                      : "NEXT QUESTION"}
                  </button>
                )}

                {!isEnded && (
                  <button
                    type="button"
                    onClick={handleToggleLeaderboard}
                    className="rounded-xl bg-[#91F0DF] px-5 py-4 font-bold text-[#21052F] hover:bg-[#ACF7EA]"
                  >
                    {liveState.showLeaderboard
                      ? "HIDE LEADERBOARD"
                      : "VIEW LEADERBOARD"}
                  </button>
                )}

                {isEnded && (
                  <div className="rounded-xl bg-green-100 px-5 py-4 text-center font-bold text-green-800">
                    Quiz finished
                  </div>
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

              {liveState.showLeaderboard && (
                <section className="mt-8 border-t border-gray-200 pt-6">
                  <h3 className="text-2xl font-bold">Leaderboard</h3>
                  <p className="mt-2 text-sm text-gray-500">
                    Sample scores for frontend testing only.
                  </p>
                  <div className="mt-4 space-y-3">
                    {demoLeaderboard.map((player, index) => (
                      <div
                        key={player.name}
                        className="flex items-center justify-between rounded-xl bg-gray-100 p-4"
                      >
                        <span className="font-semibold">
                          {index + 1}. {player.name}
                        </span>
                        <span className="font-bold">
                          {player.score} points
                        </span>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {isEnded && (
                <p className="mt-6 rounded-xl bg-purple-50 p-4 text-sm leading-6 text-[#31064D]">
                  This quiz has ended. The live state is saved in this
                  browser for the projector prototype.
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
