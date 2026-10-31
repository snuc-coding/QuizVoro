import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { participantApi } from "../services/api";

function JoinPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [pin, setPin] = useState(() =>
    String(searchParams.get("pin") || "").replace(/\D/g, "").slice(0, 8)
  );
  const [nickname, setNickname] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    const cleanPin = pin.replace(/\D/g, "").slice(0, 8);
    const cleanNick = nickname.trim();

    if (cleanPin.length < 4 || cleanPin.length > 8) {
      setError("Please enter a valid Game PIN.");
      return;
    }

    if (!cleanNick) {
      setError("Please choose a nickname.");
      return;
    }

    setLoading(true);

    try {
      // Connect to the real backend join API
      const joinData = await participantApi.joinGame(cleanPin, cleanNick);

      // Navigate to live question/game screen with game state
      navigate(`/game/${joinData.game_id}`, {
        state: {
          gameId: joinData.game_id,
          participantId: joinData.participant_id,
          nickname: joinData.nickname,
          token: joinData.token,
          pin: cleanPin,
        },
      });
    } catch (err) {
      console.error("Join game failed:", err);
      setError(err.message || "Could not join game. Please verify the PIN and nickname.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="flex w-full max-w-md flex-col items-center">
      <h1 className="brand-font mb-1 text-center text-6xl leading-[1.15] text-white sm:text-7xl">
        Asteris!
      </h1>

      <p className="mb-7 text-center text-sm tracking-wide text-purple-100/80">
        THINK FAST. OWN THE GAME.
      </p>

      <form
        onSubmit={handleSubmit}
        className="w-full rounded-3xl bg-white px-6 py-8 text-[#31064D] shadow-2xl sm:px-9 sm:py-9"
      >
        <h2 className="nav-font mb-6 text-center text-2xl font-bold">
          JOIN GAME
        </h2>

        {error && (
          <div className="mb-5 rounded-xl bg-red-50 p-3.5 text-sm font-medium text-red-700 border border-red-200">
            {error}
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label htmlFor="game-pin" className="mb-1 block text-xs font-bold text-gray-500 uppercase">
              Game PIN
            </label>
            <input
              id="game-pin"
              type="text"
              inputMode="numeric"
              autoComplete="off"
              maxLength={8}
              value={pin}
              onChange={(event) => {
                setPin(event.target.value.replace(/\D/g, "").slice(0, 8));
                setError("");
              }}
              placeholder="ENTER GAME PIN"
              disabled={loading}
              className="min-h-[64px] w-full rounded-2xl border-2 border-[#E0DDE5] bg-[#F0EFF2] px-4 text-center text-xl font-bold tracking-widest text-[#31064D] outline-none transition focus:border-[#7950A8]"
              required
            />
          </div>

          <div>
            <label htmlFor="player-nickname" className="mb-1 block text-xs font-bold text-gray-500 uppercase">
              Nickname
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
              placeholder="ENTER NICKNAME"
              disabled={loading}
              className="min-h-[64px] w-full rounded-2xl border-2 border-[#E0DDE5] bg-[#F0EFF2] px-4 text-center text-lg font-bold text-[#31064D] outline-none transition focus:border-[#7950A8]"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="brand-font mt-4 min-h-[64px] w-full rounded-2xl bg-[#31064D] text-xl font-bold text-white shadow-lg transition hover:bg-[#49205C] disabled:opacity-50"
          >
            {loading ? "JOINING..." : "ENTER GAME"}
          </button>
        </div>
      </form>
    </section>
  );
}

export default JoinPage;
