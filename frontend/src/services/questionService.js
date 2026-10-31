import { participantApi } from "./api";

// Get current open question for a live game
export async function getCurrentQuestion(gameId) {
  return participantApi.getCurrentQuestion(gameId);
}

// Submit participant answer to real backend API
export async function submitAnswer({ gameId, questionId, optionId = null, selectedOption = null }) {
  return participantApi.submitAnswer(gameId, {
    question_id: questionId,
    option_id: optionId,
    selected_option: selectedOption,
  });
}
