import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import AdminNav from "../components/AdminNav";
import { quizApi, hostApi } from "../services/api";

function QuizManagementPage() {
  const navigate = useNavigate();

  const [quizzes, setQuizzes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [quizToDelete, setQuizToDelete] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  const loadQuizzes = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await quizApi.listQuizzes();
      setQuizzes(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Could not load quizzes from backend:", err);
      setError(err.message || "Could not load quizzes from server.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadQuizzes();
  }, [loadQuizzes]);

  // Host / Select a quiz: creates or prepares a game session
  async function handleSelectQuiz(quiz) {
    setActionLoading(true);
    try {
      // Create a game on the backend for this quiz
      const game = await hostApi.createGame(quiz.id);
      sessionStorage.setItem("asterisSelectedQuizId", String(quiz.id));
      sessionStorage.setItem("quizvoro_active_game", JSON.stringify(game));

      navigate(`/admin/host?quizId=${quiz.id}&gameId=${game.id}`);
    } catch (err) {
      console.error("Failed to initialize game:", err);
      alert(err.message || "Failed to create game session on server.");
    } finally {
      setActionLoading(false);
    }
  }

  function handleAskDelete(quiz) {
    setError("");
    setQuizToDelete(quiz);
  }

  async function handleConfirmDelete() {
    if (!quizToDelete) return;
    setActionLoading(true);
    try {
      await quizApi.deleteQuiz(quizToDelete.id);
      setQuizToDelete(null);
      await loadQuizzes();
    } catch (err) {
      console.error("Failed to delete quiz:", err);
      setError(err.message || "The quiz could not be deleted.");
    } finally {
      setActionLoading(false);
    }
  }

  function handleCancelDelete() {
    setQuizToDelete(null);
  }

  return (
    <main className="min-h-screen px-4 py-10 text-[#31064D] sm:px-8">
      <div className="mx-auto max-w-5xl">
        <AdminNav />

        <div className="mt-8 mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="brand-font text-3xl font-bold text-white sm:text-4xl">
              Saved Quizzes
            </h1>
            <p className="mt-1 text-sm text-purple-100/80">
              Manage, host, and launch quizzes stored in your backend database.
            </p>
          </div>

          <button
            type="button"
            onClick={() => navigate("/admin/create")}
            className="rounded-xl bg-[#91F0DF] px-5 py-2.5 font-bold text-[#31064D] transition hover:brightness-105"
          >
            + CREATE NEW QUIZ
          </button>
        </div>

        {error && (
          <div className="mb-6 rounded-2xl bg-red-100 p-4 text-red-800 border border-red-300">
            {error}
          </div>
        )}

        {loading ? (
          <div className="rounded-2xl bg-white/95 p-12 text-center shadow-xl">
            <p className="font-semibold text-lg text-gray-600">Loading quizzes from backend...</p>
          </div>
        ) : quizzes.length === 0 ? (
          <div className="rounded-2xl bg-white/95 p-12 text-center shadow-xl">
            <p className="text-xl font-bold text-[#31064D]">No quizzes found</p>
            <p className="mt-2 text-sm text-gray-600">
              You haven't created any quizzes yet. Click the button below to get started!
            </p>
            <button
              type="button"
              onClick={() => navigate("/admin/create")}
              className="mt-6 rounded-xl bg-[#C51E50] px-6 py-3 font-bold text-white transition hover:bg-[#D6295D]"
            >
              CREATE YOUR FIRST QUIZ
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {quizzes.map((quiz) => (
              <div
                key={quiz.id}
                className="flex flex-col gap-4 rounded-2xl border border-white/20 bg-white/95 p-5 shadow-lg sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <h2 className="nav-font text-2xl font-bold">{quiz.title}</h2>
                  {quiz.description && (
                    <p className="mt-1 text-sm text-gray-600">{quiz.description}</p>
                  )}
                  <p className="mt-2 text-xs font-semibold text-purple-900/60">
                    ID: {quiz.id} • Created: {new Date(quiz.created_at).toLocaleDateString()}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    disabled={actionLoading}
                    onClick={() => handleSelectQuiz(quiz)}
                    className="rounded-xl bg-[#31064D] px-5 py-2.5 font-bold text-white transition hover:bg-[#49205C] disabled:opacity-50"
                  >
                    HOST LIVE →
                  </button>

                  <button
                    type="button"
                    disabled={actionLoading}
                    onClick={() => handleAskDelete(quiz)}
                    className="rounded-xl border border-red-300 px-4 py-2.5 font-semibold text-red-600 transition hover:bg-red-50 disabled:opacity-50"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Delete Confirmation Modal */}
        {quizToDelete && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
            <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
              <h3 className="text-xl font-bold text-[#31064D]">Delete Quiz</h3>
              <p className="mt-3 text-sm text-gray-600">
                Are you sure you want to delete <span className="font-bold">"{quizToDelete.title}"</span>? This will permanently remove all associated rounds and questions.
              </p>
              <div className="mt-6 flex justify-end gap-3">
                <button
                  type="button"
                  disabled={actionLoading}
                  onClick={handleCancelDelete}
                  className="rounded-xl border border-gray-300 px-4 py-2 font-semibold text-gray-700 hover:bg-gray-100"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={actionLoading}
                  onClick={handleConfirmDelete}
                  className="rounded-xl bg-red-600 px-5 py-2 font-bold text-white hover:bg-red-700 disabled:opacity-50"
                >
                  {actionLoading ? "Deleting..." : "Delete"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

export default QuizManagementPage;
