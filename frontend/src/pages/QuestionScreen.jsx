
import { useCallback, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { submitMockAnswer } from "../services/questionService";
import AnswerResultsChart from "../components/game/AnswerResultsChart";

const LIVE_STATE_KEY = "asterisLiveQuizState";
const QUIZZES_KEY = "asterisQuizzes";
const DEMO_VOTES = [10, 20, 55, 15];

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

  if (indexValue !== undefined && indexValue !== null && indexValue !== "") {
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
    if (index >= 0 && index < options.length) return index;
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
      ? savedQuizzes.find((item) => String(item.id) === String(quizId))
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

    window.addEventListener("storage", handleStorageChange);
    return () => window.removeEventListener("storage", handleStorageChange);
  }, [loadQuiz]);

  const questions = Array.isArray(quiz?.questions) ? quiz.questions : [];
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
        setError("Your answer could not be submitted. Please try again.");
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

  if (liveState.status === "ended") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#080710] px-4 text-center text-white">
        <div>
          <h1 className="brand-font mb-4 text-4xl">Asteris!</h1>
          <h2 className="text-3xl font-extrabold">Quiz ended</h2>
          <p className="mt-3 text-purple-200">Thanks for participating!</p>
        </div>
      </main>
    );
  }

  if (liveState.showLeaderboard) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#080710] px-4 text-center text-white">
        <div>
          <h1 className="brand-font mb-4 text-4xl">Asteris!</h1>
          <h2 className="text-3xl font-extrabold">Leaderboard</h2>
          <p className="mt-3 text-purple-200">
            The host is showing the leaderboard.
          </p>
          <p className="mt-2 text-sm text-purple-300">
            Scores will appear when score tracking is connected.
          </p>
        </div>
      </main>
    );
  }

  if (liveState.status !== "running") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#080710] px-4 text-center text-white">
        <div>
          <h1 className="brand-font mb-4 text-4xl">Asteris!</h1>
          <h2 className="text-2xl font-extrabold">Get ready!</h2>
          <p className="mt-3 text-purple-200">
            {quiz.title || quiz.name || "Your quiz"} will begin when the host starts.
          </p>
          <p className="mt-2 text-sm text-purple-300">Keep this page open.</p>
        </div>
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

  const rawOptions = Array.isArray(question.options) ? question.options : [];
  const options = rawOptions.map(getOptionText);
  const correctOptionIndex = getCorrectOptionIndex(question, rawOptions);

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

  const chartOptions = options.map((text, index) => ({
    id: `${question.id ?? questionIndex}-${index}`,
    label: String.fromCharCode(65 + index),
    text,
    votes: DEMO_VOTES[index] ?? 0,
    isCorrect: correctOptionIndex === index,
  }));

  const demoTotalAnswers = chartOptions.reduce(
    (sum, option) => sum + option.votes,
    0
  );

  const timerPercentage = Math.max(
    0,
    Math.min(100, (timeLeft / duration) * 100)
  );

  const timerColor = timeLeft <= 5 ? "#FB4568" : "#D946EF";

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
                  timeLeft <= 5 ? "text-rose-400" : "text-white"
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
                const colors = optionColors[index % optionColors.length];
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
          <div className="rounded-3xl border border-purple-400/20 bg-[#15121E] p-3 sm:p-5">
            <h2 className="mb-1 text-center text-xl font-extrabold uppercase tracking-[0.18em] text-purple-200">
              RESULTS
            </h2>
            <AnswerResultsChart
              options={chartOptions}
              totalAnswers={demoTotalAnswers}
            />
          </div>
        )}

        {/* Keep feedback visible before and after the timer ends. */}
        {submitted && (
          <div
            role="status"
            className={`mt-4 rounded-xl border px-4 py-4 text-center text-lg font-extrabold ${feedbackClass}`}
          >
            {feedbackText}
          </div>
        )}

        {error && (
          <p role="alert" className="mt-3 text-center text-sm text-rose-300">
            {error}
          </p>
        )}
      </section>
    </main>
  );
}

export default QuestionScreen;
