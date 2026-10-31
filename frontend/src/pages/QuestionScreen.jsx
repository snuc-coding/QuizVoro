import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useLocation, useNavigate } from "react-router-dom";
import { participantApi, API_BASE_URL } from "../services/api";
import { QuizWebSocket } from "../services/websocket";

const optionColors = [
  { card: "bg-amber-400 hover:bg-amber-500", text: "text-[#21152C]", letter: "bg-amber-950/20" },
  { card: "bg-cyan-400 hover:bg-cyan-500", text: "text-[#071923]", letter: "bg-cyan-950/20" },
  { card: "bg-lime-400 hover:bg-lime-500", text: "text-[#19200B]", letter: "bg-lime-950/20" },
  { card: "bg-rose-400 hover:bg-rose-500", text: "text-white", letter: "bg-rose-950/20" },
];

function QuestionScreen() {
  const { gameId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  // Participant session data
  const participantData =
    location.state || participantApi.getParticipantSession?.() || {};

  const token = participantData.token;
  const nickname = participantData.nickname || "Player";

  const [gameState, setGameState] = useState("lobby"); // lobby, question, answered, reveal, finished, kicked
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [questionNumber, setQuestionNumber] = useState(1);
  const [totalQuestions, setTotalQuestions] = useState(1);
  const [timeLeft, setTimeLeft] = useState(15);
  const [selectedOptionId, setSelectedOptionId] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [answerLocked, setAnswerLocked] = useState(false);
  const [myResult, setMyResult] = useState(null);
  const [error, setError] = useState("");

  const wsRef = useRef(null);
  const timerRef = useRef(null);

  // Connect Participant WebSocket
  useEffect(() => {
    if (!gameId || !token) {
      setError("No active participant session found. Please join from the home screen.");
      return;
    }

    const ws = new QuizWebSocket({
      role: "participant",
      gameId,
      token,
      onOpen: () => {
        console.log("Participant WS connected.");
      },
      onError: (err) => {
        console.warn("Participant WS error:", err);
      },
      onMessage: (event, data) => {
        if (event === "QUESTION_STARTED") {
          // SECURITY NOTE: ParticipantQuestionOut deliberately does NOT include is_correct!
          setGameState("question");
          setCurrentQuestion(data.question);
          setQuestionNumber(data.question_number);
          setTotalQuestions(data.total_questions);
          setTimeLeft(data.time_limit || 15);
          setSelectedOptionId(null);
          setAnswerLocked(false);
          setMyResult(null);

          clearInterval(timerRef.current);
          timerRef.current = setInterval(() => {
            setTimeLeft((prev) => {
              if (prev <= 1) {
                clearInterval(timerRef.current);
                return 0;
              }
              return prev - 1;
            });
          }, 1000);
        } else if (event === "ANSWER_ACK") {
          setAnswerLocked(true);
          setGameState("answered");
        } else if (event === "GAME_PAUSED") {
          clearInterval(timerRef.current);
        } else if (event === "GAME_RESUMED") {
          if (data.remaining_seconds) {
            setTimeLeft(Math.round(data.remaining_seconds));
          }
          clearInterval(timerRef.current);
          timerRef.current = setInterval(() => {
            setTimeLeft((prev) => {
              if (prev <= 1) {
                clearInterval(timerRef.current);
                return 0;
              }
              return prev - 1;
            });
          }, 1000);
        } else if (event === "ANSWER_REVEALED") {
          setGameState("reveal");
          clearInterval(timerRef.current);
          // Fetch my updated stats from backend
          participantApi
            .getMyStats(gameId)
            .then((stats) => {
              setMyResult(stats);
            })
            .catch((e) => console.warn("Failed to get my stats:", e));
        } else if (event === "PLAYER_PERSONAL_RESULT") {
          setMyResult(data);
        } else if (event === "PLAYER_KICKED") {
          setGameState("kicked");
          clearInterval(timerRef.current);
        } else if (event === "GAME_FINISHED") {
          setGameState("finished");
          clearInterval(timerRef.current);
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
      clearInterval(timerRef.current);
      ws.close();
    };
  }, [gameId, token]);

  // Answer Submission (via WS if open, fallback to REST)
  const handleSelectOption = useCallback(
    async (optionId) => {
      if (answerLocked || isSubmitting || gameState !== "question" || timeLeft <= 0) {
        return;
      }

      setSelectedOptionId(optionId);
      setIsSubmitting(true);

      try {
        if (wsRef.current && wsRef.current.ws?.readyState === WebSocket.OPEN) {
          wsRef.current.sendAnswer({
            question_id: currentQuestion.id,
            option_id: optionId,
          });
          setAnswerLocked(true);
          setGameState("answered");
        } else {
          // Fallback to REST API endpoint
          await participantApi.submitAnswer(gameId, {
            question_id: currentQuestion.id,
            option_id: optionId,
          });
          setAnswerLocked(true);
          setGameState("answered");
        }
      } catch (err) {
        console.error("Answer submission failed:", err);
        alert(err.message || "Failed to lock in your answer.");
      } finally {
        setIsSubmitting(false);
      }
    },
    [answerLocked, isSubmitting, gameState, timeLeft, currentQuestion, gameId]
  );

  if (error) {
    return (
      <main className="quiz-background flex min-h-screen flex-col items-center justify-center p-6 text-white text-center">
        <h2 className="text-2xl font-bold mb-4">Asteris</h2>
        <p className="text-red-300 max-w-sm mb-6">{error}</p>
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
    <main className="quiz-background flex min-h-screen flex-col items-center justify-between p-4 sm:p-6 text-white">
      {/* Top Header */}
      <header className="flex w-full max-w-md items-center justify-between border-b border-white/20 pb-4">
        <div className="flex items-center gap-2">
          <span className="font-bold text-lg">{nickname}</span>
        </div>
        {myResult && (
          <div className="rounded-full bg-white/20 px-3 py-1 text-sm font-bold">
            {myResult.score || 0} pts
          </div>
        )}
      </header>

      {/* Main Game Card / State */}
      <div className="w-full max-w-md my-auto py-6">
        {/* Waiting Lobby */}
        {gameState === "lobby" && (
          <div className="rounded-3xl bg-white p-8 text-[#31064D] text-center shadow-2xl">
            <span className="text-5xl">🎮</span>
            <h2 className="brand-font mt-4 text-3xl font-bold">You're In!</h2>
            <p className="mt-2 text-gray-600">
              Welcome, <strong className="font-bold">{nickname}</strong>!
            </p>
            <div className="mt-6 rounded-2xl bg-[#31064D] p-6 text-white text-center">
              <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-4 border-white/30 border-t-[#91F0DF]" />
              <p className="font-bold text-lg">Waiting for host...</p>
              <p className="text-xs text-purple-200 mt-1">
                The quiz will begin as soon as the host starts.
              </p>
            </div>
          </div>
        )}

        {/* Active Question View */}
        {gameState === "question" && currentQuestion && (
          <div className="space-y-4">
            <div className="flex items-center justify-between text-sm font-bold">
              <span>Question {questionNumber} of {totalQuestions}</span>
              <span className={`rounded-full px-3 py-1 font-extrabold ${
                timeLeft <= 5 ? "bg-red-500 text-white animate-pulse" : "bg-white/20 text-[#91F0DF]"
              }`}>
                ⏱ {timeLeft}s
              </span>
            </div>

            <div className="rounded-3xl bg-white p-6 text-[#31064D] shadow-2xl">
              <h2 className="text-xl font-bold leading-snug">
                {currentQuestion.question_text}
              </h2>
              {currentQuestion.media_url && (
                <div className="mt-4 flex justify-center">
                  <img
                    src={`${API_BASE_URL}${currentQuestion.media_url}`}
                    alt="Media"
                    className="max-h-48 rounded-xl object-contain shadow"
                  />
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 pt-2">
              {currentQuestion.options?.map((opt, idx) => {
                const scheme = optionColors[idx % optionColors.length];
                const isSelected = selectedOptionId === opt.id;

                return (
                  <button
                    key={opt.id}
                    type="button"
                    disabled={isSubmitting || timeLeft <= 0}
                    onClick={() => handleSelectOption(opt.id)}
                    className={`min-h-[80px] rounded-2xl p-4 font-bold text-lg shadow-lg flex items-center gap-3 transition transform active:scale-95 text-left ${scheme.card} ${scheme.text} ${
                      isSelected ? "ring-4 ring-white" : ""
                    }`}
                  >
                    <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl font-black ${scheme.letter}`}>
                      {String.fromCharCode(65 + idx)}
                    </span>
                    <span className="flex-1 leading-tight">{opt.option_text}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Answer Locked View */}
        {gameState === "answered" && (
          <div className="rounded-3xl bg-white p-8 text-[#31064D] text-center shadow-2xl">
            <span className="text-5xl">🔒</span>
            <h2 className="brand-font mt-4 text-3xl font-bold">Answer Locked In!</h2>
            <p className="mt-2 text-gray-600">
              Hold tight! Results will appear once time runs out or the host reveals the answer.
            </p>
            <div className="mt-6 flex items-center justify-center gap-2 text-sm text-purple-700 font-semibold">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-purple-300 border-t-purple-700" />
              <span>Waiting for reveal...</span>
            </div>
          </div>
        )}

        {/* Reveal Results View */}
        {gameState === "reveal" && (
          <div className="rounded-3xl bg-white p-8 text-[#31064D] text-center shadow-2xl">
            <h2 className="brand-font text-3xl font-bold">Question Scored!</h2>
            {myResult?.last_result ? (
              <div className="mt-4">
                {myResult.last_result.is_correct ? (
                  <div className="rounded-2xl bg-green-100 p-4 text-green-800">
                    <span className="text-4xl">🎉</span>
                    <p className="font-bold text-xl mt-2">Correct!</p>
                    <p className="text-sm">+{myResult.last_result.points_awarded || 0} points</p>
                  </div>
                ) : (
                  <div className="rounded-2xl bg-red-100 p-4 text-red-800">
                    <span className="text-4xl">❌</span>
                    <p className="font-bold text-xl mt-2">Incorrect</p>
                    <p className="text-sm">Better luck on the next one!</p>
                  </div>
                )}
              </div>
            ) : (
              <p className="mt-4 text-gray-600">Waiting for next question from host...</p>
            )}

            {myResult && (
              <div className="mt-6 border-t pt-4 flex justify-around">
                <div>
                  <p className="text-xs text-gray-500 uppercase font-bold">Total Score</p>
                  <p className="text-2xl font-extrabold text-[#31064D]">{myResult.score || 0}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase font-bold">Rank</p>
                  <p className="text-2xl font-extrabold text-[#C51E50]">#{myResult.rank || "-"}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase font-bold">Streak</p>
                  <p className="text-2xl font-extrabold text-amber-500">{myResult.streak || 0} 🔥</p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Kicked View */}
        {gameState === "kicked" && (
          <div className="rounded-3xl bg-white p-8 text-[#31064D] text-center shadow-2xl">
            <span className="text-5xl">🚫</span>
            <h2 className="brand-font mt-4 text-2xl font-bold text-red-600">Removed from game</h2>
            <p className="mt-2 text-gray-600">The host has removed you from this quiz session.</p>
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
          <div className="rounded-3xl bg-white p-8 text-[#31064D] text-center shadow-2xl">
            <span className="text-5xl">🏆</span>
            <h2 className="brand-font mt-4 text-3xl font-bold">Game Over!</h2>
            <p className="mt-2 text-gray-600">Thanks for playing, {nickname}!</p>
            {myResult && (
              <div className="my-6 rounded-2xl bg-[#EDE4F5] p-6 text-[#31064D]">
                <p className="text-xs font-bold uppercase tracking-widest text-[#6B5680]">Your Final Standing</p>
                <p className="brand-font text-5xl font-black mt-2 text-[#C51E50]">#{myResult.rank || 1}</p>
                <p className="text-xl font-bold mt-1">{myResult.score || 0} points</p>
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
