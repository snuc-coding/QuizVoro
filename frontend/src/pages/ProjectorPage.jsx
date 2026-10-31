import { useEffect, useState, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import { QuizWebSocket } from "../services/websocket";
import { API_BASE_URL } from "../services/api";

function ProjectorPage() {
  const [searchParams] = useSearchParams();
  const gameId = searchParams.get("gameId");
  const token = searchParams.get("token");

  const [status, setStatus] = useState("lobby"); // lobby, active, paused, reveal, finished
  const [players, setPlayers] = useState([]);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [questionNumber, setQuestionNumber] = useState(1);
  const [totalQuestions, setTotalQuestions] = useState(1);
  const [timeLeft, setTimeLeft] = useState(0);
  const [answeredCount, setAnsweredCount] = useState(0);
  const [revealedData, setRevealedData] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [error, setError] = useState("");

  const timerRef = useRef(null);

  useEffect(() => {
    if (!gameId || !token) {
      setError("Missing stage access token or game ID. Open this window from the host dashboard.");
      return;
    }

    const ws = new QuizWebSocket({
      role: "stage",
      gameId,
      token,
      onOpen: () => {
        console.log("Stage WebSocket connected.");
      },
      onError: (err) => {
        console.warn("Stage WS error:", err);
      },
      onMessage: (event, data) => {
        if (event === "PLAYER_JOINED") {
          setPlayers((prev) => {
            if (prev.some((p) => p.participant_id === data.participant_id)) return prev;
            return [...prev, { participant_id: data.participant_id, nickname: data.nickname }];
          });
        } else if (event === "PLAYER_LEFT" || event === "PLAYER_KICKED") {
          setPlayers((prev) => prev.filter((p) => p.participant_id !== data.participant_id));
        } else if (event === "QUESTION_STARTED") {
          setStatus("active");
          setCurrentQuestion(data.question);
          setQuestionNumber(data.question_number);
          setTotalQuestions(data.total_questions);
          setTimeLeft(data.time_limit || 15);
          setAnsweredCount(0);
          setRevealedData(null);

          // Clear previous countdown
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
        } else if (event === "ANSWER_COUNT_UPDATED") {
          setAnsweredCount(data.answered_count);
        } else if (event === "GAME_PAUSED") {
          setStatus("paused");
          clearInterval(timerRef.current);
        } else if (event === "GAME_RESUMED") {
          setStatus("active");
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
          setStatus("reveal");
          clearInterval(timerRef.current);
          setRevealedData(data);
        } else if (event === "LEADERBOARD_UPDATED") {
          setLeaderboard(data.entries || []);
        } else if (event === "GAME_FINISHED") {
          setStatus("finished");
          clearInterval(timerRef.current);
        }
      },
    });

    ws.connect();

    return () => {
      clearInterval(timerRef.current);
      ws.close();
    };
  }, [gameId, token]);

  const joinUrl = `${window.location.origin}/`;

  if (error) {
    return (
      <main className="quiz-background flex min-h-screen flex-col items-center justify-center p-6 text-white text-center">
        <h1 className="brand-font text-4xl mb-4">Stage Display</h1>
        <p className="text-red-300 max-w-md">{error}</p>
      </main>
    );
  }

  return (
    <main className="quiz-background min-h-screen p-6 sm:p-12 text-white flex flex-col justify-between">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-white/20 pb-4">
        <span className="brand-font text-4xl font-extrabold tracking-wider">
          Asteris
        </span>
        <div className="flex items-center gap-4">
          <span className="rounded-full bg-white/10 px-4 py-1 text-sm font-semibold tracking-widest text-[#91F0DF] uppercase">
            LIVE PROJECTOR STAGE
          </span>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 my-auto flex flex-col items-center justify-center">
        {/* Lobby View */}
        {status === "lobby" && (
          <div className="w-full max-w-4xl text-center">
            <h2 className="text-3xl sm:text-5xl font-bold tracking-tight mb-4">
              Join the game at <span className="text-[#91F0DF] underline">{window.location.host}</span>
            </h2>

            <div className="my-8 flex flex-col sm:flex-row items-center justify-center gap-10">
              <div className="rounded-3xl bg-white p-6 shadow-2xl">
                <QRCodeSVG value={joinUrl} size={220} />
              </div>
            </div>

            <p className="text-xl font-medium text-purple-200">
              {players.length} {players.length === 1 ? "player" : "players"} connected
            </p>

            <div className="mt-6 flex flex-wrap justify-center gap-3 max-h-48 overflow-y-auto">
              {players.map((p) => (
                <span
                  key={p.participant_id}
                  className="rounded-xl bg-white/20 backdrop-blur-md px-4 py-2 font-bold text-lg"
                >
                  {p.nickname}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Question View */}
        {(status === "active" || status === "paused" || status === "reveal") && currentQuestion && (
          <div className="w-full max-w-5xl">
            {/* Top metadata */}
            <div className="flex items-center justify-between mb-6">
              <span className="rounded-xl bg-white/20 px-4 py-2 text-lg font-bold">
                Question {questionNumber} / {totalQuestions}
              </span>

              {status !== "reveal" && (
                <div className={`flex items-center justify-center h-16 w-16 rounded-full border-4 font-black text-2xl ${
                  timeLeft <= 5 ? "border-red-400 text-red-300 animate-pulse" : "border-[#91F0DF] text-[#91F0DF]"
                }`}>
                  {timeLeft}
                </div>
              )}

              <span className="rounded-xl bg-white/20 px-4 py-2 text-lg font-bold">
                {answeredCount} Answers
              </span>
            </div>

            {/* Question Text */}
            <div className="rounded-3xl bg-white/95 p-8 text-[#31064D] shadow-2xl text-center mb-8">
              <h2 className="text-3xl sm:text-4xl font-bold leading-relaxed">
                {currentQuestion.question_text}
              </h2>

              {currentQuestion.media_url && (
                <div className="mt-6 flex justify-center">
                  <img
                    src={`${API_BASE_URL}${currentQuestion.media_url}`}
                    alt="Question media"
                    className="max-h-64 rounded-xl object-contain shadow"
                  />
                </div>
              )}
            </div>

            {/* Options */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {currentQuestion.options?.map((opt, idx) => {
                const colors = [
                  "bg-amber-400 text-black",
                  "bg-cyan-400 text-black",
                  "bg-lime-400 text-black",
                  "bg-rose-400 text-white",
                ];
                const cardColor = colors[idx % colors.length];
                const isRevealed = status === "reveal";
                const isCorrect = revealedData?.correct_option_id === opt.id;
                const voteCount =
                  revealedData?.distribution?.find((d) => d.option_id === opt.id)?.count || 0;

                return (
                  <div
                    key={opt.id}
                    className={`rounded-2xl p-6 shadow-xl flex items-center justify-between transition transform ${cardColor} ${
                      isRevealed && !isCorrect ? "opacity-35 scale-95" : ""
                    } ${isRevealed && isCorrect ? "ring-8 ring-green-400 scale-105" : ""}`}
                  >
                    <div className="flex items-center gap-4">
                      <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-black/20 font-black text-xl">
                        {String.fromCharCode(65 + idx)}
                      </span>
                      <span className="text-2xl font-bold">
                        {opt.option_text}
                      </span>
                    </div>

                    {isRevealed && (
                      <span className="font-extrabold text-2xl">
                        {voteCount}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Finished / Leaderboard View */}
        {status === "finished" && (
          <div className="w-full max-w-3xl text-center">
            <span className="text-6xl">🏆</span>
            <h2 className="brand-font text-5xl font-extrabold text-[#91F0DF] mt-2 mb-8">
              Podium & Leaderboard
            </h2>

            <div className="space-y-4">
              {leaderboard.slice(0, 5).map((entry, idx) => (
                <div
                  key={entry.participant_id}
                  className={`flex items-center justify-between rounded-2xl p-5 shadow-2xl ${
                    idx === 0
                      ? "bg-amber-400 text-[#31064D] scale-105 font-black text-2xl"
                      : idx === 1
                      ? "bg-slate-200 text-[#31064D] font-bold text-xl"
                      : idx === 2
                      ? "bg-amber-600 text-white font-bold text-xl"
                      : "bg-white/20 text-white font-semibold text-lg backdrop-blur-md"
                  }`}
                >
                  <div className="flex items-center gap-4">
                    <span className="w-8 text-center">#{entry.rank}</span>
                    <span>{entry.nickname}</span>
                  </div>
                  <span>{entry.score} pts</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="text-center text-xs text-purple-200/60 pt-4 border-t border-white/10">
        QuizVoro Live Presentation Stage
      </footer>
    </main>
  );
}

export default ProjectorPage;
