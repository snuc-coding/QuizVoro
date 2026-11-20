
import { useCallback, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { submitMockAnswer } from "../services/questionService";
import Leaderboard from "../components/game/Leaderboard";

const LIVE_STATE_KEY = "asterisLiveQuizState";
const QUIZZES_KEY = "asterisQuizzes";

const optionColors = [
  {
    card: "bg-amber-400",
    text: "text-[#21152C]",
    letter: "bg-amber-950/15",
  },
  {
    card: "bg-cyan-400",
    text: "text-[#071923]",
    letter: "bg-cyan-950/15",
  },
  {
    card: "bg-lime-400",
    text: "text-[#19200B]",
    letter: "bg-lime-950/15",
  },
  {
    card: "bg-rose-400",
    text: "text-[#29101A]",
    letter: "bg-rose-950/15",
  },
];

function readJSON(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key) || "null") ?? fallback;
  } catch {
    return fallback;
  }
}

function getOptionText(option) {
  if (typeof option === "string") return option;
  return option?.text ?? option?.label ?? "";
}

function getCorrectOptionIndex(question, options) {
  const markedIndex = options.findIndex(
    (option) =>
      typeof option === "object" &&
      (option?.isCorrect === true || option?.correct === true)
  );

  if (markedIndex >= 0) return markedIndex;

  const indexValue =
    question?.correctOptionIndex ??
    question?.correctAnswerIndex ??
    question?.correctIndex;

  if (
    indexValue !== undefined &&
    indexValue !== null &&
    indexValue !== ""
  ) {
    const index = Number(indexValue);

    if (
      Number.isInteger(index) &&
      index >= 0 &&
      index < options.length
    ) {
      return index;
    }
  }

  const answer =
    question?.correctAnswer ??
    question?.correctOption ??
    question?.answer ??
    question?.correct_answer;

  if (answer === undefined || answer === null || answer === "") {
    return -1;
  }

  if (typeof answer === "number") {
    return Number.isInteger(answer) &&
      answer >= 0 &&
      answer < options.length
      ? answer
      : -1;
  }

  const answerText = String(answer).trim();

  if (/^[A-Z]$/i.test(answerText)) {
    const index = answerText.toUpperCase().charCodeAt(0) - 65;

    if (index >= 0 && index < options.length) {
      return index;
    }
  }

  return options.findIndex(
    (option) =>
      getOptionText(option).trim().toLowerCase() ===
      answerText.toLowerCase()
  );
}

function QuestionScreen() {
  const location = useLocation();

  const [quiz, setQuiz] = useState(null);
  const [liveState, setLiveState] = useState(null);
  const [selectedOption, setSelectedOption] = useState(null);
  const [submitted, setSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [timeLeft, setTimeLeft] = useState(0);
  const [error, setError] = useState("");

  const loadQuiz = useCallback(() => {
    const params = new URLSearchParams(location.search);
    const requestedQuizId = params.get("quizId");

    const savedQuizzes = readJSON(QUIZZES_KEY, []);
    const savedLiveState = readJSON(LIVE_STATE_KEY, null);

    if (!Array.isArray(savedQuizzes) || savedQuizzes.length === 0) {
      setQuiz(null);
      setLiveState(null);
      setError("No saved quizzes found. Create and save a quiz first.");
      return;
    }

    const quizId =
      requestedQuizId ||
      savedLiveState?.quizId ||
      sessionStorage.getItem("asterisSelectedQuizId");

    let selectedQuiz = quizId
      ? savedQuizzes.find(
          (item) => String(item.id) === String(quizId)
        )
      : null;

    if (!selectedQuiz && !requestedQuizId) {
      selectedQuiz = savedQuizzes[0];
    }

    if (!selectedQuiz) {
      setQuiz(null);
      setLiveState(null);
      setError("The selected quiz was not found in this browser.");
      return;
    }

    setQuiz(selectedQuiz);
    setError("");

    if (
      savedLiveState &&
      String(savedLiveState.quizId) === String(selectedQuiz.id)
    ) {
      setLiveState(savedLiveState);
    } else {
      setLiveState({
        quizId: selectedQuiz.id,
        status: "ready",
        currentQuestionIndex: 0,
        showLeaderboard: false,
      });
    }
  }, [location.search]);

  useEffect(() => {
    loadQuiz();

    function handleStorageChange(event) {
      if (
        event.key === LIVE_STATE_KEY ||
        event.key === QUIZZES_KEY ||
        event.key === null
      ) {
        loadQuiz();
      }
    }

    function handleFocus() {
      loadQuiz();
    }

    window.addEventListener("storage", handleStorageChange);
    window.addEventListener("focus", handleFocus);

    return () => {
      window.removeEventListener("storage", handleStorageChange);
      window.removeEventListener("focus", handleFocus);
    };
  }, [loadQuiz]);

  const questions = Array.isArray(quiz?.questions)
    ? quiz.questions
    : [];

  const questionIndex = liveState?.currentQuestionIndex ?? 0;
  const question = questions[questionIndex] || null;
  const duration = Math.max(1, Number(question?.duration) || 20);

  useEffect(() => {
    setSelectedOption(null);
    setSubmitted(false);
    setIsSubmitting(false);
    setTimeLeft(duration);
    setError("");
  }, [questionIndex, duration, quiz?.id]);

  // The timer stops when the host changes the game state.
  // Timer expiry does not automatically advance the question.
  useEffect(() => {
    if (
      liveState?.status !== "running" ||
      !question ||
      timeLeft <= 0
    ) {
      return undefined;
    }

    const timerId = window.setTimeout(() => {
      setTimeLeft((previous) => Math.max(0, previous - 1));
    }, 1000);

    return () => window.clearTimeout(timerId);
  }, [liveState?.status, question, timeLeft]);

  async function handleSubmit() {
    if (
      selectedOption === null ||
      submitted ||
      isSubmitting ||
      timeLeft <= 0 ||
      liveState?.status !== "running" ||
      !question
    ) {
      return;
    }

    try {
      setIsSubmitting(true);
      setError("");

      const result = await submitMockAnswer({
        gameId: String(quiz.id),
        questionId: question.id ?? questionIndex,
        selectedOption,
      });

      if (result?.success) {
        setSubmitted(true);
      } else {
        setError(
          "Your answer could not be submitted. Please try again."
        );
      }
    } catch (err) {
      console.error("Answer submission failed:", err);
      setError("Could not submit your answer. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (error && !quiz) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#080710] px-4 text-white">
        <div className="max-w-md text-center">
          <p className="mb-4 text-rose-300">{error}</p>

          <button
            type="button"
            onClick={loadQuiz}
            className="rounded-xl bg-purple-600 px-5 py-3 font-bold"
          >
            Try again
          </button>
        </div>
      </main>
    );
  }

  if (!quiz || !liveState) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#080710] text-white">
        Loading quiz...
      </main>
    );
  }

  // Use the existing separate Leaderboard component.
  // It displays MOCK_PLAYERS by default until real data is integrated.
  if (liveState.showLeaderboard) {
    return (
      <Leaderboard
        quizName={quiz.title || quiz.name || "Asteris Quiz"}
        title={
          liveState.status === "ended"
            ? "Final Leaderboard"
            : "Leaderboard"
        }
      />
    );
  }

  // Show the completed screen only when the leaderboard is not visible.
  if (liveState.status === "ended") {
    return (
      <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#080710] px-4 py-8 text-center text-white">
        <div className="pointer-events-none absolute -left-24 -top-24 h-80 w-80 rounded-full bg-purple-700/25 blur-[100px]" />

        <section className="relative w-full max-w-xl rounded-3xl border border-purple-400/20 bg-[#15121E]/90 p-10 shadow-2xl">
          <h1 className="brand-font mb-6 text-4xl">Asteris!</h1>

          <div className="mb-5 text-4xl">🏆</div>

          <h2 className="text-3xl font-extrabold">
            Quiz completed!
          </h2>

          <p className="mt-4 text-purple-200">
            Thanks for participating.
          </p>
        </section>
      </main>
    );
  }

  const isResults = liveState.status === "results";
  const isReady = liveState.status === "ready";
  const isWaiting =
    !isReady &&
    !isResults &&
    liveState.status !== "running";

  // During transitions, wait for the host's next state.
  if (isResults || isReady || isWaiting) {
    const isLastQuestion =
      questionIndex >= questions.length - 1;

    let title = "Get ready!";
    let message = `${
      quiz.title || quiz.name || "Your quiz"
    } will begin when the host starts.`;

    if (isResults) {
      title = isLastQuestion
        ? "Waiting for the final leaderboard..."
        : "Waiting for the next question...";

      message = isLastQuestion
        ? "The host is preparing to reveal the final rankings. Keep this page open."
        : "The host is choosing the next step. Keep this page open.";
    } else if (isWaiting) {
      title = "Waiting for the host...";
      message =
        "The host is preparing the next part of the quiz. Keep this page open.";
    }

    return (
      <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#080710] px-4 py-8 text-white">
        <div className="pointer-events-none absolute -left-24 -top-24 h-80 w-80 rounded-full bg-purple-700/25 blur-[100px]" />

        <div className="pointer-events-none absolute -bottom-24 -right-24 h-80 w-80 rounded-full bg-violet-800/25 blur-[100px]" />

        <section className="relative w-full max-w-xl rounded-3xl border border-purple-400/20 bg-[#15121E]/90 p-8 text-center shadow-2xl sm:p-12">
          <h1 className="brand-font mb-8 text-4xl text-white sm:text-5xl">
            Asteris!
          </h1>

          <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl border border-purple-300/20 bg-purple-500/10 text-3xl">
            {isResults ? "⏳" : "🎮"}
          </div>

          <p className="mb-3 text-xs font-bold uppercase tracking-[0.25em] text-[#91F0DF]">
            {isResults ? "QUESTION COMPLETED" : "PLEASE WAIT"}
          </p>

          <h2 className="text-2xl font-extrabold sm:text-3xl">
            {title}
          </h2>

          <p className="mt-4 leading-7 text-purple-200">
            {message}
          </p>

          <div
            className="mt-8 flex justify-center gap-2"
            aria-label="Waiting"
          >
            <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-[#91F0DF]" />
            <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-purple-400 [animation-delay:150ms]" />
            <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-fuchsia-400 [animation-delay:300ms]" />
          </div>
        </section>
      </main>
    );
  }

  if (!question) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#080710] px-4 text-center text-white">
        <div>
          <h1 className="brand-font mb-3 text-3xl">Asteris!</h1>
          <p>No question is available at this position.</p>
        </div>
      </main>
    );
  }

  const rawOptions = Array.isArray(question.options)
    ? question.options
    : [];

  const options = rawOptions.map(getOptionText);
  const correctOptionIndex = getCorrectOptionIndex(
    question,
    rawOptions
  );

  const isAnswerCorrect =
    submitted &&
    correctOptionIndex >= 0 &&
    selectedOption === correctOptionIndex;

  const feedbackText = !submitted
    ? ""
    : correctOptionIndex < 0
      ? "Answer submitted!"
      : isAnswerCorrect
        ? "✓ Correct!"
        : "✕ Wrong!";

  const feedbackClass =
    correctOptionIndex < 0
      ? "border-purple-400/30 bg-purple-500/10 text-purple-200"
      : isAnswerCorrect
        ? "border-lime-400/30 bg-lime-400/10 text-lime-300"
        : "border-rose-400/30 bg-rose-400/10 text-rose-300";

  const timerPercentage = Math.max(
    0,
    Math.min(100, (timeLeft / duration) * 100)
  );

  const timerColor =
    timeLeft <= 5 ? "#FB4568" : "#D946EF";

  return (
    <main className="relative flex min-h-screen w-full justify-center overflow-hidden bg-[#080710] px-4 py-6 text-white sm:items-center">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -left-32 -top-24 h-80 w-80 rounded-full bg-purple-700/30 blur-[100px]"
      />

      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-32 -right-24 h-96 w-96 rounded-full bg-violet-800/30 blur-[110px]"
      />

      <section className="relative z-10 w-full max-w-3xl">
        <header className="mb-6 flex items-center justify-between">
          <h1 className="brand-font text-3xl text-white sm:text-4xl">
            Asteris!
          </h1>

          <span
            aria-hidden="true"
            className="flex h-12 w-12 items-center justify-center rounded-2xl border border-purple-300/25 bg-white/5 text-2xl text-purple-100"
          >
            🎮
          </span>
        </header>

        <div className="mb-4 flex items-center justify-between gap-2 text-sm">
          <span className="font-semibold tracking-wide text-purple-200">
            QUESTION {questionIndex + 1} / {questions.length}
          </span>

          <span className="rounded-full border border-purple-300/15 bg-purple-500/15 px-3 py-1 text-center text-purple-200">
            {timeLeft === 0
              ? "Time is up!"
              : isSubmitting
                ? "Submitting..."
                : submitted
                  ? "Answer submitted"
                  : "Choose an answer"}
          </span>
        </div>

        <div className="mb-5 rounded-3xl border border-purple-400/20 bg-[#15121E] px-5 py-7 text-center shadow-[0_0_35px_rgba(100,40,180,0.08)]">
          <p className="mb-3 text-xs font-bold uppercase tracking-[0.2em] text-purple-300">
            Your question
          </p>

          <h2 className="text-2xl font-extrabold leading-snug sm:text-3xl">
            {question.text ||
              question.question ||
              question.questionText ||
              "Question text unavailable"}
          </h2>
        </div>

        {timeLeft > 0 && (
          <div className="mb-6 rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-4">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-xs font-bold tracking-[0.18em] text-purple-200">
                TIME LEFT
              </span>

              <span
                className={`text-2xl font-black tabular-nums ${
                  timeLeft <= 5
                    ? "text-rose-400"
                    : "text-white"
                }`}
                role="timer"
              >
                {String(Math.floor(timeLeft / 60)).padStart(2, "0")}:
                {String(timeLeft % 60).padStart(2, "0")}
              </span>
            </div>

            <div
              className="h-2 overflow-hidden rounded-full bg-[#35204E]"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(timerPercentage)}
            >
              <div
                className="h-full rounded-full transition-all duration-1000 ease-linear"
                style={{
                  width: `${timerPercentage}%`,
                  backgroundColor: timerColor,
                }}
              />
            </div>

            {timeLeft <= 5 && !submitted && (
              <p className="mt-2 text-right text-xs font-semibold text-rose-300">
                Hurry! Time is running out.
              </p>
            )}
          </div>
        )}

        {timeLeft > 0 ? (
          <>
            <p className="mb-3 text-xs font-bold uppercase tracking-[0.18em] text-purple-200">
              Choose your answer
            </p>

            <div className="grid grid-cols-2 gap-3">
              {options.map((option, index) => {
                const colors =
                  optionColors[index % optionColors.length];

                const isSelected = selectedOption === index;

                return (
                  <button
                    key={`${index}-${option}`}
                    type="button"
                    disabled={submitted || isSubmitting}
                    onClick={() => setSelectedOption(index)}
                    aria-pressed={isSelected}
                    className={`flex min-h-28 flex-col items-center justify-center gap-3 rounded-2xl border-2 p-3 shadow-lg transition duration-150 active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-60 sm:min-h-32 ${colors.card} ${
                      isSelected
                        ? "scale-[0.98] border-white ring-4 ring-white/30"
                        : "border-transparent hover:-translate-y-0.5 hover:brightness-110"
                    }`}
                  >
                    <span
                      className={`flex h-10 w-10 items-center justify-center rounded-xl text-lg font-black ${colors.letter} ${colors.text}`}
                    >
                      {String.fromCharCode(65 + index)}
                    </span>

                    <span
                      className={`text-center text-base font-extrabold sm:text-lg ${colors.text}`}
                    >
                      {option}
                    </span>
                  </button>
                );
              })}
            </div>

            <button
              type="button"
              onClick={handleSubmit}
              disabled={
                selectedOption === null ||
                submitted ||
                isSubmitting ||
                timeLeft <= 0
              }
              className="mt-5 min-h-12 w-full rounded-2xl bg-gradient-to-r from-violet-700 to-purple-500 px-4 py-3 font-bold text-white shadow-lg shadow-purple-950/30 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {isSubmitting
                ? "SUBMITTING..."
                : submitted
                  ? "ANSWER SUBMITTED ✓"
                  : "SUBMIT ANSWER →"}
            </button>
          </>
        ) : (
          <div className="rounded-3xl border border-purple-400/20 bg-[#15121E] p-5 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-purple-500/15 text-2xl">
              ⏳
            </div>

            <h2 className="text-xl font-extrabold">Time is up!</h2>

            <p className="mt-2 text-purple-200">
              Waiting for the host to show the results or continue.
            </p>
          </div>
        )}

        {submitted && (
          <div
            role="status"
            className={`mt-4 rounded-xl border px-4 py-4 text-center text-lg font-extrabold ${feedbackClass}`}
          >
            {feedbackText}
          </div>
        )}

        {error && (
          <p
            role="alert"
            className="mt-3 text-center text-sm text-rose-300"
          >
            {error}
          </p>
        )}
      </section>
    </main>
  );
}

export default QuestionScreen;
