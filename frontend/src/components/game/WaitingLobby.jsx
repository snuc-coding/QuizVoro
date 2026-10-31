
function WaitingLobby({ nickname, pin, onBack }) {
  return (
    <section className="flex w-full max-w-md flex-col items-center">
      {/* Asteris branding */}
      <h1 className="brand-font mb-1 text-center text-6xl leading-[1.15] sm:text-7xl">
        Asteris!
      </h1>

      <p className="mb-6 text-center text-sm tracking-wide text-purple-100/80 sm:mb-7">
        THINK FAST. OWN THE GAME.
      </p>

      {/* Main waiting card */}
      <div className="w-full rounded-2xl border border-white/20 bg-[#FAF7FC] px-5 pb-6 pt-6 shadow-[0_24px_70px_rgba(12,0,25,0.35)] sm:px-7 sm:pb-7 sm:pt-7">
        <div className="mb-3 text-center text-4xl" aria-hidden="true">
          🎮
        </div>

        <h2 className="nav-font text-center text-2xl text-[#31064D] sm:text-3xl">
          YOU'RE IN!
        </h2>

        <p className="mt-2 text-center text-gray-600">
          Welcome,{" "}
          <span className="break-words font-bold">
            {nickname || "Player"}
          </span>
          !
        </p>

        {/* Game PIN */}
        <div className="mt-4 rounded-xl bg-[#EDE4F5] px-4 py-3 text-center">
          <p className="text-xs font-medium tracking-wider text-[#6B5680]">
            GAME PIN
          </p>

          <p className="mt-1 text-2xl font-bold tracking-[0.2em] text-[#31064D]">
            {pin || "--------"}
          </p>
        </div>

        {/* Waiting status */}
        <div className="mt-4 rounded-xl border border-white/10 bg-[#38204C] px-4 py-5 text-center text-white sm:py-6">
          <div
            className="mx-auto mb-3 h-9 w-9 animate-spin rounded-full border-4 border-white/20 border-t-[#D8B4FE]"
            role="status"
            aria-label="Waiting for the host"
          />

          <h3 className="nav-font text-lg text-white sm:text-xl">
            WAITING FOR THE HOST...
          </h3>

          <p className="mt-2 text-sm leading-6 text-purple-100/80">
            You're all set! The quiz will begin when the host starts the game.
          </p>
        </div>

        <p className="mt-4 text-center text-sm text-gray-500">
          Keep this screen open.
        </p>

        {/* Change nickname */}
        <button
          type="button"
          onClick={onBack}
          className="nav-font mt-4 min-h-11 w-full rounded-xl border border-[#D8D2DF] px-4 py-3 text-sm text-[#31064D] transition hover:bg-[#EDE4F5] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#7950A8] sm:text-base"
        >
          ← CHANGE NICKNAME
        </button>
      </div>
    </section>
  );
}

export default WaitingLobby;
