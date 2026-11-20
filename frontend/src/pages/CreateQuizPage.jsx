
import { useState } from "react";
import { useNavigate } from "react-router-dom";

function CreateQuizPage() {
  const navigate = useNavigate();

  const [title, setTitle] = useState("");
  const [questions, setQuestions] = useState([
    {
      id: crypto.randomUUID(),
      text: "",
      options: ["", "", "", ""],
      correctAnswer: 0,
      duration: 15,
      mediaType: "text",
      mediaUrl: "",
    },
  ]);

  function updateQuestion(questionIndex, field, value) {
    setQuestions((currentQuestions) =>
      currentQuestions.map((question, index) =>
        index === questionIndex
          ? { ...question, [field]: value }
          : question
      )
    );
  }

  function updateOption(questionIndex, optionIndex, value) {
    setQuestions((currentQuestions) =>
      currentQuestions.map((question, index) =>
        index === questionIndex
          ? {
              ...question,
              options: question.options.map((option, i) =>
                i === optionIndex ? value : option
              ),
            }
          : question
      )
    );
  }

  function addQuestion() {
    setQuestions((currentQuestions) => [
      ...currentQuestions,
      {
        id: crypto.randomUUID(),
        text: "",
        options: ["", "", "", ""],
        correctAnswer: 0,
        duration: 15,
        mediaType: "text",
        mediaUrl: "",
      },
    ]);
  }

  function removeQuestion(questionIndex) {
    setQuestions((currentQuestions) =>
      currentQuestions.filter((_, index) => index !== questionIndex)
    );
  }

  function handleLogout() {
    sessionStorage.removeItem("asterisAdminLoggedIn");
    sessionStorage.removeItem("asterisAdminUsername");
    sessionStorage.removeItem("asterisSelectedQuizId");
    navigate("/", { replace: true });
  }

  function handleSave(event) {
    event.preventDefault();

    const cleanTitle = title.trim();

    if (!cleanTitle) {
      alert("Please enter a quiz title.");
      return;
    }

    if (questions.length === 0) {
      alert("Please add at least one question.");
      return;
    }

    const hasIncompleteQuestion = questions.some(
      (question) =>
        !question.text.trim() ||
        question.options.some((option) => !option.trim()) ||
        (question.mediaType !== "text" && !question.mediaUrl.trim())
    );

    if (hasIncompleteQuestion) {
      alert(
        "Please complete every question, option, and required media URL."
      );
      return;
    }

    const savedQuiz = {
      id: crypto.randomUUID(),
      title: cleanTitle,
      questions,
      createdAt: new Date().toISOString(),
    };

    try {
      const existingQuizzes = JSON.parse(
        localStorage.getItem("asterisQuizzes") || "[]"
      );

      if (!Array.isArray(existingQuizzes)) {
        throw new Error("Saved quiz data is invalid.");
      }

      localStorage.setItem(
        "asterisQuizzes",
        JSON.stringify([...existingQuizzes, savedQuiz])
      );

      alert("Quiz saved successfully!");

      // Return to the admin dashboard after saving.
      navigate("/admin/dashboard", { replace: true });
    } catch (error) {
      console.error("Could not save quiz:", error);
      alert("Unable to save the quiz. Please try again.");
    }
  }

  function handleCancel() {
    // Discard the unsaved form and return to the admin dashboard.
    navigate("/admin/dashboard");
  }

  return (
    <main className="min-h-screen px-5 py-8 text-[#31064D] sm:px-8 lg:px-12">
      <div className="mx-auto w-full max-w-5xl">
        {/* Header: logo and logout only */}
        <header className="mb-12">
          <div className="flex min-h-[72px] items-center justify-between gap-4 border-b border-white/20 pb-6">
            <button
              type="button"
              onClick={() => navigate("/admin/dashboard")}
              className="brand-font text-4xl font-bold leading-tight text-white sm:text-5xl"
              aria-label="Go to admin dashboard"
            >
              Asteris
            </button>

            <button
              type="button"
              onClick={handleLogout}
              className="shrink-0 rounded-xl border border-white/40 px-5 py-3 font-bold text-white transition hover:bg-white/10"
            >
              LOGOUT
            </button>
          </div>

          {/* Heading with more spacing */}
          <section className="pb-4 pt-10 sm:pt-12">
            <p className="mb-3 text-sm font-bold uppercase tracking-[0.22em] text-[#91F0DF]">
              QUIZ BUILDER
            </p>

            <h2 className="brand-font text-4xl font-bold leading-tight text-white sm:text-5xl">
              Create your quiz
            </h2>

            <p className="mt-5 max-w-3xl text-base leading-8 text-white/85 sm:text-lg">
              Bring your questions to life. Add text, images, audio, or video
              and prepare your quiz for the big screen.
            </p>
          </section>
        </header>

        {/* Quiz form */}
        <form onSubmit={handleSave} className="space-y-6">
          {/* Quiz title */}
          <section className="rounded-2xl bg-white p-6 shadow-xl sm:p-8">
            <label htmlFor="quiz-title" className="mb-3 block font-bold">
              Quiz title
            </label>

            <input
              id="quiz-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="e.g. Asteris General Quiz"
              required
              className="w-full rounded-xl border border-gray-300 px-4 py-3 outline-none focus:ring-2 focus:ring-purple-300"
            />
          </section>

          {/* Questions */}
          {questions.map((question, questionIndex) => (
            <section
              key={question.id}
              className="rounded-2xl bg-white p-6 shadow-xl sm:p-8"
            >
              <div className="mb-5 flex items-center justify-between gap-3">
                <h3 className="text-xl font-bold">
                  Question {questionIndex + 1}
                </h3>

                {questions.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeQuestion(questionIndex)}
                    className="rounded-lg px-3 py-2 text-sm font-semibold text-red-600 hover:bg-red-50"
                  >
                    Remove
                  </button>
                )}
              </div>

              <label className="mb-2 block font-semibold">
                Question text
              </label>

              <textarea
                value={question.text}
                onChange={(event) =>
                  updateQuestion(questionIndex, "text", event.target.value)
                }
                placeholder="Enter your question"
                required
                rows={2}
                className="w-full rounded-xl border border-gray-300 px-4 py-3 outline-none focus:ring-2 focus:ring-purple-300"
              />

              <label className="mb-2 mt-5 block font-semibold">
                Question type
              </label>

              <select
                value={question.mediaType}
                onChange={(event) =>
                  updateQuestion(
                    questionIndex,
                    "mediaType",
                    event.target.value
                  )
                }
                className="w-full rounded-xl border border-gray-300 bg-white px-4 py-3"
              >
                <option value="text">Text only</option>
                <option value="image">Image</option>
                <option value="audio">Audio</option>
                <option value="video">Video URL</option>
                <option value="youtube">YouTube video</option>
              </select>

              {question.mediaType !== "text" && (
                <div className="mt-4">
                  <label className="mb-2 block font-semibold">
                    Media URL
                  </label>

                  <input
                    type="url"
                    value={question.mediaUrl}
                    onChange={(event) =>
                      updateQuestion(
                        questionIndex,
                        "mediaUrl",
                        event.target.value
                      )
                    }
                    placeholder="Enter an image, audio, or video URL"
                    required
                    className="w-full rounded-xl border border-gray-300 px-4 py-3"
                  />

                  <p className="mt-2 text-sm text-gray-500">
                    Use a URL accessible to the browser. Local media uploads
                    can be added later.
                  </p>
                </div>
              )}

              <label className="mb-3 mt-6 block font-semibold">
                Answer options
              </label>

              <div className="grid gap-3 sm:grid-cols-2">
                {question.options.map((option, optionIndex) => (
                  <input
                    key={optionIndex}
                    value={option}
                    onChange={(event) =>
                      updateOption(
                        questionIndex,
                        optionIndex,
                        event.target.value
                      )
                    }
                    placeholder={`Option ${optionIndex + 1}`}
                    required
                    className="w-full rounded-xl border border-gray-300 px-4 py-3"
                  />
                ))}
              </div>

              <label className="mb-2 mt-6 block font-semibold">
                Correct answer
              </label>

              <select
                value={question.correctAnswer}
                onChange={(event) =>
                  updateQuestion(
                    questionIndex,
                    "correctAnswer",
                    Number(event.target.value)
                  )
                }
                className="w-full rounded-xl border border-gray-300 bg-white px-4 py-3"
              >
                {question.options.map((option, optionIndex) => (
                  <option key={optionIndex} value={optionIndex}>
                    Option {optionIndex + 1}
                    {option.trim() ? ` — ${option}` : ""}
                  </option>
                ))}
              </select>

              <label className="mb-2 mt-6 block font-semibold">
                Time limit
              </label>

              <select
                value={question.duration}
                onChange={(event) =>
                  updateQuestion(
                    questionIndex,
                    "duration",
                    Number(event.target.value)
                  )
                }
                className="w-full rounded-xl border border-gray-300 bg-white px-4 py-3"
              >
                <option value={10}>10 seconds</option>
                <option value={15}>15 seconds</option>
                <option value={20}>20 seconds</option>
                <option value={30}>30 seconds</option>
                <option value={60}>60 seconds</option>
              </select>
            </section>
          ))}

          {/* Add question */}
          <button
            type="button"
            onClick={addQuestion}
            className="w-full rounded-xl border-2 border-dashed border-white/70 bg-white/10 px-6 py-4 font-bold text-white transition hover:bg-white/20"
          >
            + ADD ANOTHER QUESTION
          </button>

          {/* Save and cancel */}
          <div className="flex flex-col gap-3 pt-2 sm:flex-row">
            <button
              type="submit"
              className="flex-1 rounded-xl bg-[#C51E50] px-6 py-4 font-bold text-white transition hover:bg-[#D6295D]"
            >
              SAVE QUIZ
            </button>

            <button
              type="button"
              onClick={handleCancel}
              className="flex-1 rounded-xl bg-white px-6 py-4 font-bold text-[#31064D] transition hover:bg-gray-100"
            >
              CANCEL
            </button>
          </div>
        </form>
      </div>
    </main>
  );
}

export default CreateQuizPage;
