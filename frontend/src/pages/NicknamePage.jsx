
import { useState } from "react";

function NicknamePage({ pin, onContinue, onBack }) {
  const [nickname, setNickname] = useState("");
  const [error, setError] = useState("");

  function handleSubmit(event) {
    event.preventDefault();

    const cleanNickname = nickname.trim();

    if (!cleanNickname) {
      setError("Please enter your nickname.");
      return;
    }

    setError("");
    onContinue(cleanNickname);
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
        <h2 className="nav-font mb-2 text-center text-2xl font-bold">
          CHOOSE YOUR NICKNAME
        </h2>

        <p className="mb-6 text-center text-sm text-gray-500">
          Game PIN: <span className="font-bold">{pin}</span>
        </p>

        <label htmlFor="player-nickname" className="sr-only">
          Your nickname
        </label>

        <input
          id="player-nickname"
          type="text"
          autoComplete="nickname"
          maxLength={24}
          value={nickname}
          onChange={(event) => {
            setNickname(event.target.value);
            setError("");
          }}
          placeholder="YOUR NICKNAME"
          className="min-h-[76px] w-full rounded-2xl border-2 border-[#E0DDE5] bg-[#F0EFF2] px-4 text-center text-lg text-[#31064D] outline-none transition focus:border-[#7950A8]"
          required
          autoFocus
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
          CONTINUE →
        </button>

        <button
          type="button"
          onClick={onBack}
          className="mt-3 min-h-11 w-full rounded-xl border border-[#D8D2DF] px-4 py-3 text-sm text-[#31064D] transition hover:bg-[#EDE4F5]"
        >
          ← BACK
        </button>
      </form>
    </section>
  );
}

export default NicknamePage;
