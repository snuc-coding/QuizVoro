
const TOP_THREE_STYLES = [
  "border-l-4 border-l-yellow-400 bg-yellow-400/10",
  "border-l-4 border-l-slate-300 bg-slate-300/10",
  "border-l-4 border-l-orange-400 bg-orange-400/10",
];

const MEDALS = ["🥇", "🥈", "🥉"];

function Leaderboard({
  players = [],
  quizName = "Quiz",
  title = "Final Leaderboard",
}) {
  // Preserve the ranking order provided by the backend.
  const rankedPlayers = Array.isArray(players)
    ? players.slice(0, 10)
    : [];

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#0B0712] px-4 py-6 text-white sm:px-8">
      {/* Background glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-40 left-1/2 h-96 w-[700px] -translate-x-1/2 rounded-full bg-purple-700/20 blur-[120px]"
      />

      <div className="relative z-10 mx-auto max-w-4xl">
        {/* Heading */}
        <header className="mb-6 text-center">
          <div className="text-3xl" aria-hidden="true">
            🏆
          </div>

          <p className="nav-font mt-2 text-xs font-bold tracking-[0.25em] text-[#91F0DF]">
            QUIZ COMPLETE
          </p>

          <h1 className="brand-font mt-1 text-3xl font-bold sm:text-4xl">
            {title}
          </h1>

          <p className="mt-2 text-sm text-purple-200">
            {quizName}
          </p>
        </header>

        {/* Real backend leaderboard */}
        {rankedPlayers.length > 0 ? (
          <section className="overflow-hidden rounded-xl border border-purple-400/20 bg-[#171020]/95 shadow-[0_0_35px_rgba(126,34,206,0.12)]">
            {rankedPlayers.map((player, index) => (
              <div
                key={player.participant_id ?? player.id ?? index}
                className={`flex min-h-[54px] items-center gap-3 border-b border-white/[0.06] px-4 py-3 last:border-b-0 sm:px-5 ${
                  TOP_THREE_STYLES[index] ||
                  "border-l-4 border-l-transparent"
                }`}
              >
                {/* Official backend rank */}
                <span className="flex w-8 shrink-0 justify-center text-sm font-bold text-purple-200">
                  {index < 3
                    ? MEDALS[index]
                    : `#${player.rank ?? index + 1}`}
                </span>

                {/* Participant nickname */}
                <span className="min-w-0 flex-1 truncate text-sm font-semibold sm:text-base">
                  {player.nickname ||
                    player.name ||
                    `Player ${index + 1}`}
                </span>

                {/* Official backend score */}
                <span className="shrink-0 text-sm font-bold tabular-nums sm:text-base">
                  {Number(player.score || 0).toLocaleString()}
                  <span className="ml-1 text-xs font-normal text-purple-200/70">
                    pts
                  </span>
                </span>
              </div>
            ))}
          </section>
        ) : (
          <section className="rounded-xl border border-purple-400/20 bg-[#171020]/95 p-8 text-center">
            <p className="font-semibold">
              No player scores available
            </p>

            <p className="mt-2 text-sm text-purple-200/70">
              The leaderboard will appear when the backend provides participant scores.
            </p>
          </section>
        )}

        <footer className="mt-5 text-center text-xs text-purple-200/50">
          Cognition Quiz Club · Asteris 2026
        </footer>
      </div>
    </main>
  );
}

export default Leaderboard;
