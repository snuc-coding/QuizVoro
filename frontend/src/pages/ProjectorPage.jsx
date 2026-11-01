import { useEffect, useState, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import { QuizWebSocket } from "../services/websocket";
import { API_BASE_URL } from "../services/api";

function ProjectorPage() {
  const [searchParams] = useSearchParams();

  const gameId = searchParams.get("gameId");
  const token = searchParams.get("token");

  const [status, setStatus] = useState("lobby");
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

  // Build a media URL that supports relative and absolute URLs.
  const getMediaUrl = (url) => {
    if (!url) return "";

    if (/^https?:\/\//i.test(url)) {
      return url;
    }

    return `${API_BASE_URL.replace(/\/$/, "")}${
      url.startsWith("/") ? "" : "/"
    }${url}`;
  };

  // Connect to the stage WebSocket.
  useEffect(() => {
    if (!gameId || !token) {
      setError(
        "Missing stage access token or game ID. Open this screen from the host dashboard."
      );
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
        console.warn("Stage WebSocket error:", err);
      },

      onClose: () => {
        console.warn("Stage WebSocket disconnected.");
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
        } else if (
          event === "PLAYER_LEFT" ||
          event === "PLAYER_KICKED"
        ) {
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

          setTimeLeft(data.time_limit || 15);
          setAnsweredCount(0);
          setRevealedData(null);

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
          setAnsweredCount(data.answered_count || 0);
        } else if (event === "GAME_PAUSED") {
          setStatus("paused");
          clearInterval(timerRef.current);
        } else if (event === "GAME_RESUMED") {
          setStatus("active");

          if (data.remaining_seconds != null) {
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
          setLeaderboard(data.top || []);
        } else if (event === "GAME_FINISHED") {
          setStatus("finished");
          clearInterval(timerRef.current);
          setLeaderboard(data.leaderboard?.top || []);
        } else if (event === "ERROR") {
          console.error("Stage WebSocket error:", data);
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

  const isActive = status === "active";
  const isPaused = status === "paused";
  const isReveal = status === "reveal";
  const isFinished = status === "finished";

  if (error) {
    return (
      <main className="quiz-background flex min-h-screen items-center justify-center px-6 text-center text-white">
        <div className="max-w-xl rounded-3xl border border-white/10 bg-[#260638] p-10 shadow-2xl">
          <h1 className="brand-font text-4xl font-bold">
            Asteris Stage
          </h1>

          <p className="mt-5 leading-7 text-rose-200">
            {error}
          </p>

          <p className="mt-4 text-sm text-purple-200/60">
            Please reopen the projector from the host dashboard.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="quiz-background flex min-h-screen flex-col px-5 py-6 text-white sm:px-10 sm:py-8 lg:px-14">
      {/* HEADER */}
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-white/15 pb-5">
        <div>
          <h1 className="brand-font text-4xl font-extrabold tracking-wide sm:text-5xl">
            Asteris<span className="text-[#91F0DF]">!</span>
          </h1>

          <p className="nav-font mt-1 text-xs font-bold tracking-[0.25em] text-[#91F0DF]">
            QUIZVORO LIVE EXPERIENCE
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span className="flex items-center gap-2 rounded-full border border-green-400/30 bg-green-400/10 px-4 py-2 text-xs font-bold tracking-wider text-green-300">
            <span className="h-2 w-2 animate-pulse rounded-full bg-green-400" />
            LIVE STAGE
          </span>

          <span className="rounded-full border border-white/15 bg-white/10 px-4 py-2 text-xs font-bold tracking-wider text-purple-100">
            {isFinished
              ? "COMPLETED"
              : isReveal
                ? "RESULTS"
                : isPaused
                  ? "PAUSED"
                  : isActive
                    ? "IN PROGRESS"
                    : "WAITING"}
          </span>
        </div>
      </header>

      {/* MAIN CONTENT */}
      <div className="my-8 flex flex-1 flex-col justify-center">
        {/* LOBBY */}
        {status === "lobby" && (
          <section className="mx-auto w-full max-w-5xl text-center">
            <div className="mb-8">
              <span className="inline-block rounded-full border border-[#91F0DF]/30 bg-[#91F0DF]/10 px-5 py-2 text-sm font-bold tracking-widest text-[#91F0DF]">
                GET READY TO PLAY
              </span>

              <h2 className="brand-font mt-6 text-4xl font-extrabold leading-tight sm:text-6xl lg:text-7xl">
                The Quiz Is
                <span className="block text-[#91F0DF]">
                  About To Begin!
                </span>
              </h2>

              <p className="mt-5 text-lg text-purple-100/75 sm:text-xl">
                Scan the QR code or visit the join page to participate.
              </p>
            </div>

            <div className="grid items-center gap-8 rounded-3xl border border-white/15 bg-[#260638]/80 p-6 shadow-2xl backdrop-blur-xl sm:p-10 md:grid-cols-2">
              {/* QR CODE */}
              <div className="flex flex-col items-center">
                <div className="rounded-3xl bg-white p-5 shadow-2xl">
                  <QRCodeSVG
                    value={joinUrl}
                    size={230}
                    level="H"
                    includeMargin
                  />
                </div>

                <p className="mt-5 text-sm font-bold tracking-widest text-[#91F0DF]">
                  SCAN TO JOIN
                </p>

                <p className="mt-2 text-sm text-purple-100/60">
                  {window.location.host}
                </p>
              </div>

              {/* PLAYER COUNT */}
              <div className="flex flex-col items-center justify-center">
                <p className="text-sm font-bold tracking-[0.2em] text-purple-200">
                  PLAYERS CONNECTED
                </p>

                <h3 className="brand-font mt-3 text-8xl font-black text-[#91F0DF]">
                  {players.length}
                </h3>

                <p className="mt-2 text-lg text-purple-100/70">
                  {players.length === 1
                    ? "Participant"
                    : "Participants"}{" "}
                  ready
                </p>

                <div className="mt-7 w-full rounded-2xl border border-white/10 bg-white/5 p-5">
                  <p className="mb-4 text-xs font-bold tracking-widest text-purple-200">
                    JOINED PLAYERS
                  </p>

                  {players.length === 0 ? (
                    <p className="py-5 text-sm text-purple-100/50">
                      Waiting for participants to join...
                    </p>
                  ) : (
                    <div className="flex max-h-48 flex-wrap justify-center gap-2 overflow-y-auto">
                      {players.map((player) => (
                        <span
                          key={player.participant_id}
                          className="rounded-xl border border-[#91F0DF]/20 bg-[#91F0DF]/10 px-4 py-2 text-sm font-bold text-[#91F0DF]"
                        >
                          {player.nickname}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            <p className="mt-8 animate-pulse text-sm font-semibold tracking-widest text-purple-200/60">
              WAITING FOR THE HOST TO START THE QUIZ...
            </p>
          </section>
        )}

        {/* QUESTION / PAUSED / REVEAL */}
        {(isActive || isPaused || isReveal) && currentQuestion && (
          <section className="mx-auto w-full max-w-6xl">
            {/* TOP INFORMATION */}
            <div className="mb-7 flex flex-wrap items-center justify-between gap-4">
              <div className="rounded-2xl border border-white/15 bg-white/10 px-5 py-3">
                <p className="text-xs font-bold tracking-widest text-purple-200">
                  QUESTION
                </p>

                <p className="mt-1 text-2xl font-black">
                  {questionNumber}
                  <span className="text-purple-200">
                    {" "}/ {totalQuestions}
                  </span>
                </p>
              </div>

              {/* TIMER */}
              {!isReveal && (
                <div
                  className={`flex h-24 w-24 flex-col items-center justify-center rounded-full border-[5px] shadow-xl ${
                    timeLeft <= 5
                      ? "animate-pulse border-red-400 bg-red-400/10 text-red-300"
                      : "border-[#91F0DF] bg-[#91F0DF]/10 text-[#91F0DF]"
                  }`}
                >
                  <span className="text-4xl font-black tabular-nums">
                    {timeLeft}
                  </span>

                  <span className="text-[10px] font-bold tracking-widest">
                    SECONDS
                  </span>
                </div>
              )}

              {isReveal && (
                <div className="rounded-2xl border border-green-400/30 bg-green-400/10 px-6 py-4 text-center">
                  <p className="text-sm font-extrabold tracking-widest text-green-300">
                    ANSWER REVEALED
                  </p>
                </div>
              )}

              {/* ANSWER COUNT */}
              <div className="rounded-2xl border border-white/15 bg-white/10 px-5 py-3 text-right">
                <p className="text-xs font-bold tracking-widest text-purple-200">
                  RESPONSES
                </p>

                <p className="mt-1 text-2xl font-black text-[#91F0DF]">
                  {answeredCount}
                </p>
              </div>
            </div>

            {/* QUESTION CARD */}
            <div className="mb-8 rounded-3xl border border-white/20 bg-white p-7 text-center text-[#31064D] shadow-2xl sm:p-12">
              <p className="text-xs font-extrabold tracking-[0.25em] text-purple-500">
                QUESTION {questionNumber}
              </p>

              <h2 className="brand-font mt-5 text-3xl font-extrabold leading-snug sm:text-4xl lg:text-5xl">
                {currentQuestion.question_text}
              </h2>

              {/* IMAGE / AUDIO / VIDEO */}
              {currentQuestion.media_url && (
                <div className="mt-7 flex w-full justify-center">
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
                          className="max-h-72 max-w-full rounded-2xl object-contain shadow-lg"
                        />
                      );
                    }

                    if (mediaType === "audio") {
                      return (
                        <audio
                          controls
                          preload="metadata"
                          className="w-full max-w-xl"
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
                          className="max-h-96 w-full rounded-2xl object-contain shadow-lg"
                          src={mediaUrl}
                        >
                          Your browser does not support video playback.
                        </video>
                      );
                    }

                    return (
                      <p className="text-sm text-red-200">
                        Unsupported question media type: {mediaType}
                      </p>
                    );
                  })()}
                </div>
              )}
            </div>

            {/* ANSWER OPTIONS */}
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              {currentQuestion.options?.map((opt, idx) => {
                const colors = [
                  "bg-amber-400 text-black",
                  "bg-cyan-400 text-black",
                  "bg-lime-400 text-black",
                  "bg-rose-500 text-white",
                ];

                const cardColor = colors[idx % colors.length];

                const isCorrect =
                  revealedData?.correct_option_id === opt.id;

                const voteCount =
                  revealedData?.distribution?.find(
                    (d) => d.option_id === opt.id
                  )?.count || 0;

                return (
                  <div
                    key={opt.id}
                    className={`flex min-h-28 items-center justify-between gap-4 rounded-2xl p-5 shadow-xl transition-all duration-500 sm:p-7 ${cardColor} ${
                      isReveal && !isCorrect
                        ? "scale-[0.97] opacity-40"
                        : ""
                    } ${
                      isReveal && isCorrect
                        ? "scale-[1.02] ring-8 ring-green-400"
                        : ""
                    }`}
                  >
                    <div className="flex min-w-0 items-center gap-4">
                      <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-black/15 text-2xl font-black">
                        {String.fromCharCode(65 + idx)}
                      </span>

                      <span className="break-words text-xl font-extrabold sm:text-2xl">
                        {opt.option_text}
                      </span>
                    </div>

                    {isReveal && (
                      <div className="shrink-0 text-right">
                        <p className="text-3xl font-black">
                          {voteCount}
                        </p>

                        <p className="text-xs font-bold uppercase">
                          Votes
                        </p>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* PAUSED MESSAGE */}
            {isPaused && (
              <div className="mt-8 rounded-2xl border border-amber-300/30 bg-amber-400/10 p-5 text-center">
                <p className="text-2xl font-extrabold text-amber-300">
                  QUIZ PAUSED
                </p>

                <p className="mt-2 text-purple-100/70">
                  Please wait while the host resumes the quiz.
                </p>
              </div>
            )}

            {/* REVEAL MESSAGE */}
            {isReveal && (
              <div className="mt-8 rounded-2xl border border-green-400/30 bg-green-400/10 p-5 text-center">
                <p className="text-2xl font-extrabold text-green-300">
                  CORRECT ANSWER!
                </p>

                <p className="mt-2 text-purple-100/70">
                  The correct option is highlighted above.
                </p>
              </div>
            )}
          </section>
        )}

        {/* FINAL LEADERBOARD */}
        {isFinished && (
          <section className="mx-auto w-full max-w-4xl text-center">
            <div className="mb-8">
              <span className="text-7xl">🏆</span>

              <h2 className="brand-font mt-4 text-4xl font-black text-[#91F0DF] sm:text-6xl">
                Quiz Complete!
              </h2>

              <p className="mt-3 text-lg text-purple-100/70">
                Congratulations to all our participants.
              </p>
            </div>

            <div className="rounded-3xl border border-white/15 bg-[#260638]/85 p-5 shadow-2xl sm:p-9">
              <div className="mb-7">
                <p className="text-xs font-bold tracking-[0.25em] text-[#91F0DF]">
                  FINAL STANDINGS
                </p>

                <h3 className="brand-font mt-2 text-3xl font-bold">
                  Leaderboard
                </h3>
              </div>

              {leaderboard.length === 0 ? (
                <div className="rounded-2xl bg-white/5 px-5 py-12">
                  <p className="text-xl font-bold text-purple-100">
                    No scores recorded yet.
                  </p>

                  <p className="mt-2 text-sm text-purple-200/60">
                    The final leaderboard is currently empty.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {leaderboard.slice(0, 5).map((entry, idx) => (
                    <div
                      key={entry.participant_id}
                      className={`flex items-center justify-between gap-4 rounded-2xl p-5 shadow-xl transition ${
                        idx === 0
                          ? "scale-[1.02] bg-amber-400 text-[#31064D]"
                          : idx === 1
                            ? "bg-slate-200 text-[#31064D]"
                            : idx === 2
                              ? "bg-amber-700 text-white"
                              : "border border-white/10 bg-white/10 text-white"
                      }`}
                    >
                      <div className="flex min-w-0 items-center gap-4">
                        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-black/10 text-xl font-black">
                          {idx === 0
                            ? "🥇"
                            : idx === 1
                              ? "🥈"
                              : idx === 2
                                ? "🥉"
                                : `#${entry.rank}`}
                        </span>

                        <div className="min-w-0 text-left">
                          <p className="truncate text-lg font-extrabold sm:text-2xl">
                            {entry.nickname}
                          </p>

                          <p className="text-xs font-semibold opacity-70">
                            RANK #{entry.rank}
                          </p>
                        </div>
                      </div>

                      <div className="shrink-0 text-right">
                        <p className="text-2xl font-black sm:text-3xl">
                          {entry.score}
                        </p>

                        <p className="text-xs font-bold uppercase opacity-70">
                          Points
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <p className="mt-8 text-sm font-semibold tracking-widest text-[#91F0DF]">
                THANK YOU FOR PLAYING ASTERIS!
              </p>
            </div>
          </section>
        )}
      </div>

      {/* FOOTER */}
      <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-5 text-xs text-purple-200/50">
        <span className="font-bold tracking-widest">
          QUIZVORO
        </span>

        <span>
          Asteris Live Presentation Stage
        </span>

        <span>
          {isFinished ? "EVENT COMPLETED" : "LIVE EVENT"}
        </span>
      </footer>
    </main>
  );
}

export default ProjectorPage;