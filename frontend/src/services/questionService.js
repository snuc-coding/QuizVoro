
import { dummyQuestions } from "../data/questions";
import { apiRequest } from "./api";

// Keep true until the backend is ready.
const USE_MOCK_DATA = true;

// Get a question by its index.
export async function getCurrentQuestion(gameId, questionIndex = 0) {
  if (USE_MOCK_DATA) {
    // Return the requested mock question.
    return dummyQuestions[questionIndex] ?? null;
  }

  // Real backend request.
  // The backend API contract may need adjustment later.
  return apiRequest(
    `/api/v1/games/${gameId}/current-question`
  );
}

// Submit an answer using mock behavior for now.
export async function submitMockAnswer({
  gameId,
  questionId,
  selectedOption,
}) {
  console.log("Mock answer submitted:", {
    gameId,
    questionId,
    selectedOption,
  });

  return {
    success: true,
    message: "Answer received (mock)",
  };
}
