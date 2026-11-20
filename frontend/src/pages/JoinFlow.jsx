
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import JoinPage from "./JoinPage";
import WaitingLobby from "../components/game/WaitingLobby";

function JoinFlow() {
  const [searchParams] = useSearchParams();

  const [participant, setParticipant] = useState(null);

  function handleJoin({ pin, nickname }) {
    const cleanPin = String(pin || "").replace(/\D/g, "").slice(0, 8);
    const cleanNickname = String(nickname || "").trim();

    if (cleanPin.length !== 8 || !cleanNickname) {
      return;
    }

    setParticipant({
      pin: cleanPin,
      nickname: cleanNickname,
    });
  }

  if (participant) {
    return (
      <main className="flex min-h-screen w-full items-center justify-center px-4 py-8">
        <WaitingLobby
          nickname={participant.nickname}
          pin={participant.pin}
          onBack={() => setParticipant(null)}
        />
      </main>
    );
  }

  return (
    <main className="flex min-h-screen w-full items-center justify-center px-4 py-8">
      <JoinPage
        key={searchParams.get("pin") || "manual-join"}
        initialPin={searchParams.get("pin") || ""}
        onJoin={handleJoin}
      />
    </main>
  );
}

export default JoinFlow;
