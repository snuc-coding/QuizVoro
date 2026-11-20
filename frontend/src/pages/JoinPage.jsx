
import { useState } from "react";

function JoinPage({ initialPin = "", onJoin }) {
  const [pin, setPin] = useState(() =>
    String(initialPin).replace(/\D/g, "").slice(0, 8)
  );
  const [error, setError] = useState("");

  function handleSubmit(event) {
    event.preventDefault();

    const cleanPin = pin.replace(/\D/g, "").slice(0, 8);

    if (cleanPin.length !== 8) {
      setError("Please enter a valid 8-digit Game PIN.");
      return;
    }

    setError("");
    onJoin?.(cleanPin);
  }

  return (
    <section className="flex w-full max-w-md flex-col items-center">
      <h1 className="brand-font mb-1 text-center text-6xl leading-[1.15] sm:text-7xl">
        Asteris!
      </h1>

      <p className="mb-7 text-center text-sm tracking-wide text-purple-100/80">
        THINK FAST. OWN THE GAME.
      </p>

      <form
        onSubmit={handleSubmit}
        className="w-full rounded-2xl bg-white px-5 py-7 text-[#31064D] shadow-2xl sm:px-9 sm:py-8"
      >
        <h2 className="nav-font mb-6 text-center text-2xl font-bold">
          JOIN GAME
        </h2>

        <label htmlFor="game-pin" className="sr-only">
          8-digit Game PIN
        </label>

        <input
          id="game-pin"
          type="text"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={8}
          value={pin}
          onChange={(event) => {
            setPin(event.target.value.replace(/\D/g, "").slice(0, 8));
            setError("");
          }}
          placeholder="ENTER 8-DIGIT PIN"
          className="min-h-[76px] w-full rounded-2xl border-2 border-[#E0DDE5] bg-[#F0EFF2] px-4 text-center text-lg text-[#31064D] outline-none transition focus:border-[#7950A8]"
          required
        />

        {error && (
          <p role="alert" className="mt-3 text-center text-sm text-red-600">
            {error}
          </p>
        )}

        <button
          type="submit"
          className="nav-font mt-5 min-h-[68px] w-full rounded-2xl bg-[#21112A] px-4 py-4 text-lg font-bold text-white transition hover:bg-[#38204C]"
        >
          JOIN GAME →
        </button>
      </form>

      <p className="mt-7 text-center text-sm text-purple-100/90">
        No account needed. Just enter and play.
      </p>
    </section>
  );
}

export default JoinPage;
