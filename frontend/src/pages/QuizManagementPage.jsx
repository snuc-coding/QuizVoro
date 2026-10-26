
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

function QuizManagementPage() {
  const navigate = useNavigate();

  const [quizzes, setQuizzes] = useState([]);
  const [quizToDelete, setQuizToDelete] = useState(null);
  const [deleteError, setDeleteError] = useState("");

  useEffect(() => {
    loadQuizzes();
  }, []);

  function loadQuizzes() {
    try {
      const saved = JSON.parse(
        localStorage.getItem("asterisQuizzes") || "[]"
      );

      setQuizzes(Array.isArray(saved) ? saved : []);
    } catch (error) {
      console.error("Could not load saved quizzes:", error);
      setQuizzes([]);
      setDeleteError("Could not load saved quizzes.");
    }
  }

  function handleLogout() {
    sessionStorage.removeItem("asterisAdminLoggedIn");
    sessionStorage.removeItem("asterisAdminUsername");
    sessionStorage.removeItem("asterisSelectedQuizId");

    navigate("/", { replace: true });
  }

  // Save the selected quiz and open presentation controls.
  function handleSelectQuiz(quiz) {
    sessionStorage.setItem(
      "asterisSelectedQuizId",
      String(quiz.id)
    );

    navigate("/admin/presentation");
  }

  function handleAskDelete(quiz) {
    setDeleteError("");
    setQuizToDelete(quiz);
  }

  function handleConfirmDelete() {
    if (!quizToDelete) return;

    try {
      const saved = JSON.parse(
        localStorage.getItem("asterisQuizzes") || "[]"
      );

      if (!Array.isArray(saved)) {
        throw new Error("Saved quiz data is invalid.");
      }

      const updatedQuizzes = saved.filter(
        (quiz) => String(quiz.id) !== String(quizToDelete.id)
      );

      localStorage.setItem(
        "asterisQuizzes",
        JSON.stringify(updatedQuizzes)
      );

      setQuizzes(updatedQuizzes);

      const selectedQuizId = sessionStorage.getItem(
        "asterisSelectedQuizId"
      );

      if (selectedQuizId === String(quizToDelete.id)) {
        sessionStorage.removeItem("asterisSelectedQuizId");
      }

      setQuizToDelete(null);
      setDeleteError("");
    } catch (error) {
      console.error("Could not delete quiz:", error);
      setDeleteError(
        "The quiz could not be deleted. Please try again."
      );
    }
  }

  function handleCancelDelete() {
    setQuizToDelete(null);
    setDeleteError("");
  }

  return (
    <main className="min-h-screen px-4 py-10 text-[#31064D] sm:px-8">
      <section className="mx-auto max-w-5xl">
        <header className="mb-12">
          <div className="mb-10 flex items-center justify-between gap-4 border-b border-white/20 pb-6">
            <button
              type="button"
              onClick={() => navigate("/admin/dashboard")}
              className="brand-font text-4xl font-bold tracking-wide text-white sm:text-5xl"
              aria-label="Go to admin dashboard"
            >
              Asteris
            </button>

            <button
              type="button"
              onClick={handleLogout}
              className="rounded-xl border border-white/40 px-5 py-3 font-bold text-white transition hover:bg-white/10"
            >
              LOGOUT
            </button>
          </div>

          <div className="pt-8">
            <p className="mb-3 text-sm font-bold uppercase tracking-[0.25em] text-[#91F0DF]">
              QUIZ HOSTING
            </p>

            <h2 className="brand-font text-4xl font-bold text-white sm:text-5xl">
              Present a quiz
            </h2>

            <p className="mt-5 max-w-3xl text-base leading-8 text-white/85 sm:text-lg">
              Choose a saved quiz to prepare for your live presentation.
              You can also delete quizzes you no longer need.
            </p>
          </div>
        </header>

        {deleteError && (
          <p
            role="alert"
            className="mb-5 rounded-xl bg-red-100 p-4 font-semibold text-red-700"
          >
            {deleteError}
          </p>
        )}

        {quizzes.length === 0 ? (
          <div className="rounded-2xl bg-white p-8 text-center shadow-xl sm:p-10">
            <h3 className="text-xl font-bold">
              No quizzes available to present.
            </h3>

            <p className="mt-3 text-gray-600">
              Create and save your first quiz to see it here.
            </p>

            <button
              type="button"
              onClick={() => navigate("/admin/create")}
              className="mt-6 rounded-xl bg-[#C51E50] px-6 py-3 font-bold text-white transition hover:bg-[#D6295D]"
            >
              CREATE A QUIZ
            </button>
          </div>
        ) : (
          <div className="space-y-5">
            {quizzes.map((quiz) => (
              <article
                key={quiz.id}
                className="flex flex-col justify-between gap-5 rounded-2xl bg-white p-6 shadow-xl sm:flex-row sm:items-center sm:p-8"
              >
                <div className="min-w-0">
                  <h3 className="break-words text-xl font-bold sm:text-2xl">
                    {quiz.title}
                  </h3>

                  <p className="mt-2 text-sm text-gray-600">
                    {quiz.questions?.length ?? 0} questions
                  </p>
                </div>

                <div className="flex shrink-0 flex-col gap-3 sm:flex-row">
                  <button
                    type="button"
                    onClick={() => handleSelectQuiz(quiz)}
                    className="rounded-xl bg-[#31064D] px-6 py-3 font-bold text-white transition hover:bg-[#49205C]"
                  >
                    SELECT QUIZ
                  </button>

                  <button
                    type="button"
                    onClick={() => handleAskDelete(quiz)}
                    className="rounded-xl border border-red-300 bg-white px-6 py-3 font-bold text-red-700 transition hover:bg-red-50"
                  >
                    DELETE
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}

        <button
          type="button"
          onClick={() => navigate("/admin/dashboard")}
          className="mt-8 w-full rounded-xl border border-white/50 bg-white/10 px-6 py-4 font-semibold text-white transition hover:bg-white/20"
        >
          BACK TO ADMIN DASHBOARD
        </button>
      </section>

      {quizToDelete && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4 py-8 backdrop-blur-sm"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              handleCancelDelete();
            }
          }}
        >
          <section
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="delete-dialog-title"
            aria-describedby="delete-dialog-description"
            className="w-full max-w-md rounded-3xl bg-white p-7 text-[#31064D] shadow-2xl sm:p-9"
          >
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-red-100 text-2xl text-red-700">
              !
            </div>

            <h2
              id="delete-dialog-title"
              className="brand-font text-2xl font-bold sm:text-3xl"
            >
              Delete this quiz?
            </h2>

            <p
              id="delete-dialog-description"
              className="mt-4 leading-7 text-gray-600"
            >
              Are you sure you want to delete{" "}
              <strong className="text-[#31064D]">
                "{quizToDelete.title}"
              </strong>
              ? This action cannot be undone.
            </p>

            <div className="mt-7 flex flex-col-reverse gap-3 sm:flex-row">
              <button
                type="button"
                onClick={handleCancelDelete}
                className="flex-1 rounded-xl border border-gray-300 px-5 py-3 font-bold transition hover:bg-gray-100"
              >
                CANCEL
              </button>

              <button
                type="button"
                onClick={handleConfirmDelete}
                className="flex-1 rounded-xl bg-red-600 px-5 py-3 font-bold text-white transition hover:bg-red-700"
              >
                YES, DELETE
              </button>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}

export default QuizManagementPage;
