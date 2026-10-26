
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import QuestionMedia from "../components/game/QuestionMedia";

const LIVE_STATE_KEY = "asterisLiveQuizState";
const QUIZZES_KEY = "asterisQuizzes";
const GAME_PIN_PREFIX = "asterisGamePin_";

function generateGamePin() {
  return String(
    Math.floor(10000000 + Math.random() * 90000000)
  );
}

function getOrCreateGamePin(quizId) {
  const storageKey = `${GAME_PIN_PREFIX}${quizId}`;
  let pin = localStorage.getItem(storageKey);

  if (/^\d{8}$/.test(pin || "")) {
    return pin;
  }

  pin = generateGamePin();
  localStorage.setItem(storageKey, pin);
  return pin;
}

function ProjectorPage() {
  const navigate = useNavigate();

  const [quiz, setQuiz] = useState(null);
  const [liveState, setLiveState] = useState(null);
  const [gamePin, setGamePin] = useState("");
  const [error, setError] = useState("");
  const [timeLeft, setTimeLeft] = useState(0);

  // Load the quiz and its saved Game PIN.
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const quizId =
        params.get("quizId") ||
        sessionStorage.getItem("asterisSelectedQuizId");

      const savedQuizzes = JSON.parse(
        localStorage.getItem(QUIZZES_KEY) || "[]"
      );

      const selectedQuiz = Array.isArray(savedQuizzes)
        ? savedQuizzes.find(
            (item) => String(item.id) === String(quizId)
          )
        : null;

      if (!selectedQuiz || !selectedQuiz.questions?.length) {
        setError("The selected quiz could not be loaded.");
        return;
      }

      const pin = getOrCreateGamePin(selectedQuiz.id);
      setQuiz(selectedQuiz);
      setGamePin(pin);

      const savedState = JSON.parse(
        localStorage.getItem(LIVE_STATE_KEY) || "null"
      );

      if (
        savedState &&
        String(savedState.quizId) === String(selectedQuiz.id)
      ) {
        setLiveState(savedState);
      } else {
        setLiveState({
          quizId: selectedQuiz.id,
          gamePin: pin,
          status: "ready",
          currentQuestionIndex: 0,
          showLeaderboard: false,
          updatedAt: Date.now(),
        });
      }
    } catch (err) {
      console.error("Projector initialization failed:", err);
      setError("Unable to load the quiz.");
    }
  }, []);

  // Receive updates from the admin tab.
  useEffect(() => {
    function handleStorageChange(event) {
      if (event.key === QUIZZES_KEY && event.newValue) {
        try {
          const quizzes = JSON.parse(event.newValue);
          const quizId = new URLSearchParams(
            window.location.search
          ).get("quizId");

          const updatedQuiz = quizzes.find(
            (item) => String(item.id) === String(quizId)
          );

          if (updatedQuiz) {
            setQuiz(updatedQuiz);
          }
        } catch (err) {
          console.error("Quiz update failed:", err);
        }
      }

      if (event.key !== LIVE_STATE_KEY) return;

      try {
        const updatedState = event.newValue
          ? JSON.parse(event.newValue)
          : null;

        if (
          updatedState &&
          quiz &&
          String(updatedState.quizId) === String(quiz.id)
        ) {
          setLiveState(updatedState);

          if (/^\d{8}$/.test(updatedState.gamePin || "")) {
            setGamePin(updatedState.gamePin);
          }
        }
      } catch (err) {
        console.error("Live state update failed:", err);
      }
    }

    window.addEventListener("storage", handleStorageChange);

    return () => {
      window.removeEventListener("storage", handleStorageChange);
    };
  }, [quiz]);

  const questionIndex = liveState?.currentQuestionIndex ?? 0;
  const question = quiz?.questions?.[questionIndex] ?? null;
  const status = liveState?.status ?? "ready";

  // Reset the projector timer when the active question changes.
  useEffect(() => {
    if (!question || status !== "running") {
      setTimeLeft(Number(question?.duration) || 15);
      return;
    }

    const duration = Math.max(1, Number(question.duration) || 15);
    setTimeLeft(duration);

    const timerId = window.setInterval(() => {
      setTimeLeft((previous) => Math.max(0, previous - 1));
    }, 1000);

    return () => window.clearInterval(timerId);
  }, [question, questionIndex, status]);

  if (error) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#080710] px-5 text-white">
        <section className="max-w-xl rounded-2xl border border-purple-300/25 bg-[#1B1525] p-8">
          <h1 className="brand-font text-3xl font-bold">
            Projector unavailable
          </h1>
          <p className="mt-4">{error}</p>
          <button
            type="button"
            onClick={() => navigate("/admin/quizzes")}
            className="mt-6 rounded-xl bg-[#C51E50] px-6 py-3 font-bold"
          >
            RETURN TO SAVED QUIZZES
          </button>
        </section>
      </main>
    );
  }

  if (!quiz || !liveState || !gamePin) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#080710] text-white">
        Loading quiz...
      </main>
    );
  }

  // Quiz ended screen.
  if (status === "ended") {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center bg-[#080710] px-5 text-center text-white">
        <h1 className="brand-font text-5xl font-bold">Asteris!</h1>
        <h2 className="mt-8 text-4xl font-black">Quiz ended</h2>
        <p className="mt-4 text-purple-200">
          Thank you for participating!
        </p>
      </main>
    );
  }

  // Leaderboard screen.
  if (liveState.showLeaderboard) {
    return (
      <main className="flex min-h-screen flex-col items-center bg-[#080710] px-5 py-12 text-white">
        <h1 className="brand-font text-4xl font-bold">Asteris!</h1>
        <h2 className="mt-8 text-3xl font-black">Leaderboard</h2>
        <p className="mt-3 text-purple-200">
          Participant scores will be connected later.
        </p>
      </main>
    );
  }

  // Waiting lobby with QR code and eight-digit PIN.
  if (status === "ready") {
    const joinUrl =
      `${window.location.origin}/join?pin=${encodeURIComponent(gamePin)}`;

    return (
      <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#080710] px-5 py-10 text-white">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -left-32 -top-24 h-96 w-96 rounded-full bg-purple-700/30 blur-[110px]"
        />

        <div
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-32 -right-24 h-96 w-96 rounded-full bg-fuchsia-700/20 blur-[110px]"
        />

        <section className="relative z-10 w-full max-w-5xl rounded-3xl border border-purple-300/20 bg-[#15121E]/95 p-6 text-center shadow-2xl sm:p-10">
          <h1 className="brand-font text-4xl font-bold sm:text-5xl">
            Asteris!
          </h1>

          <p className="mt-4 text-sm font-bold uppercase tracking-[0.25em] text-purple-300">
            Cognition Quiz Club
          </p>

          <h2 className="mt-6 text-3xl font-black sm:text-4xl">
            Join the Quiz!
          </h2>

          <p className="mt-3 text-purple-200">
            {quiz.title || quiz.name || "Live Quiz"}
          </p>

          <div className="mt-8 grid items-center gap-8 md:grid-cols-2">
            <div className="flex flex-col items-center">
              <div className="rounded-2xl bg-white p-4">
                <QRCodeSVG
                  value={joinUrl}
                  size={220}
                  level="H"
                  includeMargin
                />
              </div>

              <p className="mt-4 font-bold">SCAN TO JOIN</p>
              <p className="mt-2 max-w-xs text-sm text-purple-200">
                Scan the QR code with your phone camera.
              </p>
            </div>

            <div className="flex flex-col items-center justify-center">
              <p className="text-sm font-bold uppercase tracking-[0.2em] text-purple-300">
                GAME PIN
              </p>

              <div className="mt-4 w-full rounded-2xl border border-fuchsia-400/40 bg-purple-500/10 px-3 py-5 sm:px-5">
                <p className="whitespace-nowrap text-center text-3xl font-black tracking-[0.15em] sm:text-4xl md:text-5xl">
                  {gamePin}
                </p>
              </div>

              <p className="mt-4 text-purple-200">
                Questions: {quiz.questions.length}
              </p>

              <div className="mt-8 animate-pulse">
                <span className="inline-block h-2.5 w-2.5 rounded-full bg-lime-400" />
                <span className="ml-2 font-semibold text-lime-300">
                  Waiting for host to start...
                </span>
              </div>
            </div>
          </div>

          <p className="mt-10 border-t border-white/10 pt-5 text-sm text-purple-200/80">
            Keep this screen open. The quiz will begin when the host starts.
          </p>
        </section>
      </main>
    );
  }

  if (!question) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#080710] text-white">
        No question is available.
      </main>
    );
  }

  const duration = Math.max(1, Number(question.duration) || 15);
  const timerPercentage = Math.max(
    0,
    Math.min(100, (timeLeft / duration) * 100)
  );
  const timerColor = timeLeft <= 5 ? "#FB4568" : "#E522E8";

  const hasMedia =
    question.mediaType !== "text" && Boolean(question.mediaUrl);

  const options = Array.isArray(question.options)
    ? question.options
    : [];

  const optionColors = [
    ["border-amber-400", "bg-amber-400/10", "bg-amber-400/20"],
    ["border-cyan-400", "bg-cyan-400/10", "bg-cyan-400/20"],
    ["border-lime-400", "bg-lime-400/10", "bg-lime-400/20"],
    ["border-rose-400", "bg-rose-400/10", "bg-rose-400/20"],
  ];

  return (
    <main className="relative min-h-screen overflow-x-hidden bg-[#080710] text-white lg:h-dvh lg:min-h-0 lg:overflow-hidden">
      <div className="relative z-10 mx-auto flex min-h-screen w-full max-w-[1920px] flex-col px-4 py-3 sm:px-6 lg:h-full lg:min-h-0 lg:px-8 xl:px-10">
        <header className="flex shrink-0 items-center justify-between gap-4 border-b border-white/10 pb-3">
          <div>
            <h1 className="brand-font text-3xl font-bold sm:text-4xl">
              Asteris!
            </h1>
            <p className="mt-1 text-xs tracking-[0.22em] text-purple-200 sm:text-sm">
              LIVE QUIZ · {quiz.title || quiz.name}
            </p>
          </div>

          <div className="rounded-xl border border-purple-300/25 px-5 py-2 text-center">
            <p className="text-xs tracking-wider text-purple-200">
              QUESTION
            </p>
            <p className="text-2xl font-black sm:text-3xl">
              {questionIndex + 1}
              <span className="mx-2 text-purple-400">/</span>
              {quiz.questions.length}
            </p>
          </div>
        </header>

        <section
          className={`grid flex-1 grid-cols-1 gap-4 py-4 lg:min-h-0 lg:gap-6 ${
            hasMedia
              ? "lg:grid-cols-[1.3fr_0.7fr]"
              : "lg:grid-cols-[1.2fr_0.8fr]"
          }`}
        >
          <div className="flex min-w-0 flex-col gap-4 lg:min-h-0">
            <article className="flex min-w-0 flex-1 flex-col justify-center rounded-2xl border border-purple-300/25 bg-[#1B1525]/95 px-5 py-6 sm:px-8">
              <p className="mb-3 text-sm font-bold uppercase tracking-wider text-purple-300">
                Your question
              </p>
              <h2 className="text-2xl font-black leading-tight sm:text-3xl lg:text-4xl">
                {question.text || question.question || question.questionText}
              </h2>
              <div className="mt-4 h-1 w-12 rounded-full bg-fuchsia-500" />
            </article>

            {hasMedia && (
              <article className="flex min-h-64 flex-1 items-center justify-center overflow-hidden rounded-2xl border border-purple-300/25 bg-[#120D1C] p-3">
                <QuestionMedia
                  type={question.mediaType}
                  url={question.mediaUrl}
                />
              </article>
            )}
          </div>

          <div className="flex min-w-0 flex-col justify-center gap-5">
            <div className="flex flex-col items-center">
              <div
                className="flex h-36 w-36 items-center justify-center rounded-full p-[7px]"
                style={{
                  background: `conic-gradient(${timerColor} ${timerPercentage * 3.6}deg, #35204E ${timerPercentage * 3.6}deg)`,
                }}
                role="timer"
                aria-label={`${timeLeft} seconds remaining`}
              >
                <div className="flex h-full w-full flex-col items-center justify-center rounded-full bg-[#140D20]">
                  <p className="text-xs font-bold tracking-widest text-purple-200">
                    TIME LEFT
                  </p>
                  <p
                    className={`text-4xl font-black ${
                      timeLeft <= 5 ? "text-rose-400" : "text-white"
                    }`}
                  >
                    {String(Math.floor(timeLeft / 60)).padStart(2, "0")}:
                    {String(timeLeft % 60).padStart(2, "0")}
                  </p>
                </div>
              </div>

              <p className="mt-3 text-sm text-purple-200">
                {timeLeft === 0 ? "Time is up!" : "Choose your answer"}
              </p>
            </div>

            <div>
              <h3 className="mb-3 text-center text-sm font-bold uppercase tracking-widest text-purple-200">
                Answer options
              </h3>

              <div className="grid grid-cols-2 gap-3">
                {options.map((option, index) => {
                  const [border, background, letter] =
                    optionColors[index % optionColors.length];

                  const optionText =
                    typeof option === "string"
                      ? option
                      : option.text || option.label || "";

                  return (
                    <div
                      key={`${index}-${optionText}`}
                      className={`flex min-h-[68px] min-w-0 items-center gap-3 rounded-xl border ${border} ${background} p-3`}
                    >
                      <span
                        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${letter} font-black`}
                      >
                        {String.fromCharCode(65 + index)}
                      </span>
                      <span className="break-words font-bold">
                        {optionText}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </section>

        <footer className="border-t border-white/10 py-2 text-center text-sm text-purple-200/80">
          Cognition Quiz Club · Asteris 2026
        </footer>
      </div>
    </main>
  );
}

export default ProjectorPage;
