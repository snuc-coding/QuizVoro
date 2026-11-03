
const PODIUM_CONFIG = [
  {
    // Rank 1: Gold styling and first-place trophy/crown visual + Certificate Recipient
    container:
      "border-2 border-yellow-400 bg-gradient-to-r from-yellow-500/20 via-yellow-400/10 to-transparent shadow-[0_0_20px_rgba(250,204,21,0.25)]",
    rankBadge: "bg-yellow-400 text-black font-extrabold shadow-md",
    nameColor: "text-yellow-200 font-bold text-base sm:text-lg",
    scoreColor: "text-yellow-300 font-extrabold",
    icon: "👑",
    medal: "🥇",
    certBadge: "bg-yellow-400/20 text-yellow-300 border border-yellow-400/40",
    label: "1st Place Winner",
  },
  {
    // Rank 2: Silver styling + Certificate Recipient
    container:
      "border-2 border-slate-300 bg-gradient-to-r from-slate-400/20 via-slate-300/10 to-transparent shadow-[0_0_15px_rgba(203,213,225,0.2)]",
    rankBadge: "bg-slate-300 text-slate-900 font-extrabold shadow-md",
    nameColor: "text-slate-100 font-bold sm:text-base",
    scoreColor: "text-slate-200 font-bold",
    icon: "🥈",
    medal: "🥈",
    certBadge: "bg-slate-300/20 text-slate-200 border border-slate-300/40",
    label: "2nd Place",
  },
  {
    // Rank 3: Bronze styling + Certificate Recipient
    container:
      "border-2 border-amber-600 bg-gradient-to-r from-amber-700/25 via-amber-600/10 to-transparent shadow-[0_0_15px_rgba(217,119,6,0.2)]",
    rankBadge: "bg-amber-600 text-white font-extrabold shadow-md",
    nameColor: "text-amber-200 font-bold sm:text-base",
    scoreColor: "text-amber-300 font-bold",
    icon: "🥉",
    medal: "🥉",
    certBadge: "bg-amber-600/20 text-amber-300 border border-amber-600/40",
    label: "3rd Place",
  },
];

function Leaderboard({
  players = [],
  quizName = "Quiz",
  title = "Top 5 Leaderboard",
}) {
  // Enforce strictly Top 5 participants based on backend ranking.
  const topFivePlayers = Array.isArray(players)
    ? players.slice(0, 5)
    : [];

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#0B0712] px-4 py-6 text-white sm:px-8">
      {/* Background glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-40 left-1/2 h-96 w-[700px] -translate-x-1/2 rounded-full bg-purple-700/20 blur-[120px]"
      />

      <div className="relative z-10 mx-auto max-w-3xl">
        {/* Heading */}
        <header className="mb-6 text-center">
          <div className="text-4xl" aria-hidden="true">
            🏆
          </div>

          <p className="nav-font mt-2 text-xs font-bold tracking-[0.25em] text-[#91F0DF]">
            OFFICIAL RESULTS
          </p>

          <h1 className="brand-font mt-1 text-3xl font-bold sm:text-4xl">
            {title}
          </h1>

          <p className="mt-2 text-sm text-purple-200">
            {quizName}
          </p>
        </header>

        {/* Real backend leaderboard (strictly Top 5) */}
        {topFivePlayers.length > 0 ? (
          <section className="space-y-3">
            {topFivePlayers.map((player, index) => {
              const rank = Number(player.rank ?? index + 1);
              const isTopThree = rank <= 3;
              const podium = PODIUM_CONFIG[rank - 1];

              return (
                <div
                  key={player.participant_id ?? player.id ?? index}
                  className={`flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-2xl p-4 transition ${
                    isTopThree && podium
                      ? podium.container
                      : "border border-purple-400/20 bg-[#171020]/90 text-gray-200"
                  }`}
                >
                  {/* Left: Rank & Participant Display Name */}
                  <div className="flex items-center gap-3.5 min-w-0">
                    <span
                      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-sm ${
                        isTopThree && podium
                          ? podium.rankBadge
                          : "bg-purple-900/50 text-purple-200 font-bold"
                      }`}
                    >
                      {isTopThree && podium ? podium.icon : `#${rank}`}
                    </span>

                    <div className="min-w-0 flex-1 truncate">
                      <div className="flex items-center gap-2">
                        <span
                          className={`truncate ${
                            isTopThree && podium
                              ? podium.nameColor
                              : "text-white font-medium text-base"
                          }`}
                        >
                          {player.display_name ||
                            player.nickname ||
                            player.name ||
                            `Player ${rank}`}
                        </span>

                        {player.is_anonymous && (
                          <span className="shrink-0 rounded-md bg-purple-950/70 px-1.5 py-0.5 text-[10px] font-semibold text-[#91F0DF] border border-[#91F0DF]/30">
                            Anon
                          </span>
                        )}
                      </div>

                      {/* Certificate eligibility indicator for Top 3 */}
                      {isTopThree && (
                        <div className="mt-1 flex items-center gap-2">
                          <span
                            className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-bold ${
                              podium?.certBadge
                            }`}
                          >
                            🎓 Certificate Recipient
                          </span>
                          <span className="hidden sm:inline text-xs text-purple-300/70">
                            {podium?.label}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Right: Score */}
                  <div className="flex sm:flex-col items-center sm:items-end justify-between border-t border-white/[0.08] sm:border-t-0 pt-2 sm:pt-0">
                    <span className="text-xs text-purple-300 sm:hidden">Score</span>
                    <span
                      className={`text-lg sm:text-xl tabular-nums ${
                        isTopThree && podium
                          ? podium.scoreColor
                          : "text-purple-100 font-bold"
                      }`}
                    >
                      {Number(player.score || 0).toLocaleString()}
                      <span className="ml-1 text-xs font-normal text-purple-200/70">
                        pts
                      </span>
                    </span>
                  </div>
                </div>
              );
            })}
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

        <footer className="mt-6 text-center text-xs text-purple-200/50">
          Cognition Quiz Club · Asteris 2026
        </footer>
      </div>
    </main>
  );
}

export default Leaderboard;
