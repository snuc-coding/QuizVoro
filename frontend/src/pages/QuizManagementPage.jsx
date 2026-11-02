
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

  // Host / Select a quiz
  async function handleSelectQuiz(quiz) {
    setActionLoading(true);

    try {
      const game = await hostApi.createGame(quiz.id);

      sessionStorage.setItem(
        "asterisSelectedQuizId",
        String(quiz.id)
      );

      sessionStorage.setItem(
        "quizvoro_active_game",
        JSON.stringify(game)
      );

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
    <main className="quiz-background min-h-screen px-5 py-8 text-white sm:px-8 lg:px-12">
      <div className="mx-auto w-full max-w-6xl">

        {/* HEADER */}
        <AdminNav />

        {/* PAGE INTRO */}
        <section className="mb-9 mt-10 sm:mb-10 sm:mt-12">
          <p className="nav-font text-xs font-bold uppercase tracking-[0.3em] text-[#91F0DF]">
            QUIZ HOSTING
          </p>

          <h1 className="brand-font mt-2 text-4xl font-bold leading-tight text-white sm:text-5xl">
            Present a quiz
          </h1>

          <p className="mt-4 max-w-2xl text-sm leading-7 text-purple-100/80 sm:text-base">
            Choose a saved quiz to prepare for your live presentation.
            You can also delete quizzes you no longer need.
          </p>

          {/* CREATE BUTTON */}
          <div className="mt-6 flex justify-start sm:justify-end">
            <button
              type="button"
              onClick={() => navigate("/admin/create")}
              className="nav-font rounded-xl bg-[#91F0DF] px-5 py-3 font-bold text-[#31064D] shadow-lg transition duration-200 hover:-translate-y-0.5 hover:bg-[#ACF7EA]"
            >
              + CREATE NEW QUIZ
            </button>
          </div>
        </section>

        {/* ERROR MESSAGE */}
        {error && (
          <div
            role="alert"
            className="mb-6 rounded-2xl border border-red-300 bg-red-100 p-4 text-red-800 shadow-sm"
          >
            {error}
          </div>
        )}

        {/* LOADING */}
        {loading ? (
          <div className="rounded-2xl bg-white/95 p-12 text-center shadow-xl">
            <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-4 border-purple-200 border-t-[#31064D]" />

            <p className="text-lg font-semibold text-gray-600">
              Loading quizzes from backend...
            </p>
          </div>
        ) : quizzes.length === 0 ? (
          /* EMPTY STATE */
          <div className="rounded-2xl bg-white/95 p-12 text-center shadow-xl">
            <p className="text-xl font-bold text-[#31064D]">
              No quizzes found
            </p>

            <p className="mt-2 text-sm text-gray-600">
              You haven't created any quizzes yet. Click below to get started!
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
          /* QUIZ CARDS */
          <div className="space-y-4">
            {quizzes.map((quiz) => (
              <div
                key={quiz.id}
                className="flex flex-col gap-5 rounded-2xl border border-white/30 bg-white/95 p-5 text-[#31064D] shadow-lg transition duration-200 hover:-translate-y-0.5 hover:shadow-xl sm:flex-row sm:items-center sm:justify-between sm:p-6"
              >
                {/* QUIZ DETAILS */}
                <div className="min-w-0">
                  <h2 className="brand-font text-2xl font-bold text-[#321044]">
                    {quiz.title}
                  </h2>

                  {quiz.description && (
                    <p className="mt-2 text-sm text-gray-600">
                      {quiz.description}
                    </p>
                  )}

                  <p className="mt-2 text-xs font-semibold text-purple-800/60">
                    ID: {quiz.id} • Created:{" "}
                    {quiz.created_at
                      ? new Date(quiz.created_at).toLocaleDateString()
                      : "Date unavailable"}
                  </p>
                </div>

                {/* ACTION BUTTONS */}
                <div className="flex shrink-0 flex-wrap items-center gap-3">
                  <button
                    type="button"
                    disabled={actionLoading}
                    onClick={() => handleSelectQuiz(quiz)}
                    className="nav-font rounded-xl bg-[#31064D] px-6 py-3 font-bold text-white shadow-sm transition hover:bg-[#49205C] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {actionLoading ? "PLEASE WAIT..." : "SELECT QUIZ"}
                  </button>

                  <button
                    type="button"
                    disabled={actionLoading}
                    onClick={() => handleAskDelete(quiz)}
                    className="nav-font rounded-xl border border-red-300 bg-white px-5 py-3 font-bold text-red-600 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    DELETE
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* DELETE CONFIRMATION MODAL */}
        {quizToDelete && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
            <div className="w-full max-w-md rounded-2xl bg-white p-6 text-[#31064D] shadow-2xl sm:p-8">
              <h3 className="brand-font text-2xl font-bold">
                Delete Quiz?
              </h3>

              <p className="mt-3 text-sm leading-6 text-gray-600">
                Are you sure you want to delete{" "}
                <span className="font-bold text-[#31064D]">
                  "{quizToDelete.title}"
                </span>
                ? This will permanently remove all associated rounds and questions.
              </p>

              <div className="mt-7 flex justify-end gap-3">
                <button
                  type="button"
                  disabled={actionLoading}
                  onClick={handleCancelDelete}
                  className="rounded-xl border border-gray-300 px-5 py-2.5 font-semibold text-gray-700 transition hover:bg-gray-100 disabled:opacity-50"
                >
                  CANCEL
                </button>

                <button
                  type="button"
                  disabled={actionLoading}
                  onClick={handleConfirmDelete}
                  className="rounded-xl bg-red-600 px-5 py-2.5 font-bold text-white transition hover:bg-red-700 disabled:opacity-50"
                >
                  {actionLoading ? "DELETING..." : "DELETE"}
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
