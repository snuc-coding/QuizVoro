import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { quizApi, clearAdminToken } from "../services/api";

function CreateQuizPage() {
  const navigate = useNavigate();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const [questions, setQuestions] = useState([
    {
      id: crypto.randomUUID(),
      text: "",
      options: ["", "", "", ""],
      correctAnswer: 0,
      duration: 15,
      points: 1000,
      mediaFile: null,
      mediaPreview: "",
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

  function handleFileChange(questionIndex, file) {
    if (!file) {
      updateQuestion(questionIndex, "mediaFile", null);
      updateQuestion(questionIndex, "mediaPreview", "");
      return;
    }
    const previewUrl = URL.createObjectURL(file);
    setQuestions((currentQuestions) =>
      currentQuestions.map((question, index) =>
        index === questionIndex
          ? { ...question, mediaFile: file, mediaPreview: previewUrl }
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
        points: 1000,
        mediaFile: null,
        mediaPreview: "",
      },
    ]);
  }

  function removeQuestion(questionIndex) {
    setQuestions((currentQuestions) =>
      currentQuestions.filter((_, index) => index !== questionIndex)
    );
  }

  function handleLogout() {
    clearAdminToken();
    sessionStorage.removeItem("asterisSelectedQuizId");
    navigate("/", { replace: true });
  }

  async function handleSave(event) {
    event.preventDefault();
    setError("");

    const cleanTitle = title.trim();
    if (!cleanTitle) {
      setError("Please enter a quiz title.");
      return;
    }

    if (questions.length === 0) {
      setError("Please add at least one question.");
      return;
    }

    const hasIncompleteQuestion = questions.some(
      (question) =>
        !question.text.trim() ||
        question.options.some((option) => !option.trim())
    );

    if (hasIncompleteQuestion) {
      setError("Please complete every question and all 4 options.");
      return;
    }

    setSubmitting(true);

    try {
      // 1. Create Quiz in Backend
      const createdQuiz = await quizApi.createQuiz({
        title: cleanTitle,
        description: description.trim() || null,
      });

      // 2. Create Default Round 1
      const createdRound = await quizApi.createRound(createdQuiz.id, {
        title: "Round 1",
        description: "General Round",
        round_number: 1,
      });

      // 3. Create Questions & Upload Media if any
      for (let i = 0; i < questions.length; i++) {
        const q = questions[i];
        const formattedOptions = q.options.map((optText, optIdx) => ({
          option_text: optText.trim(),
          is_correct: optIdx === Number(q.correctAnswer),
        }));

        const createdQ = await quizApi.createQuestion(createdRound.id, {
          question_text: q.text.trim(),
          question_type: "MCQ",
          time_limit: Math.max(5, Math.min(300, Number(q.duration) || 15)),
          points: Math.max(0, Math.min(10000, Number(q.points) || 1000)),
          question_order: i + 1,
          options: formattedOptions,
        });

        // Upload media file if attached
        if (q.mediaFile) {
          try {
            await quizApi.uploadMedia(createdQ.id, q.mediaFile);
          } catch (uploadErr) {
            console.warn(`Media upload warning for question ${i + 1}:`, uploadErr);
          }
        }
      }

      alert("Quiz successfully created and saved to the backend!");
      navigate("/admin/quizzes", { replace: true });
    } catch (err) {
      console.error("Failed to save quiz to backend:", err);
      setError(err.message || "Failed to save quiz to backend. Please check connectivity.");
    } finally {
      setSubmitting(false);
    }
  }

  function handleCancel() {
    navigate("/admin/dashboard");
  }

  return (
    <main className="min-h-screen px-5 py-8 text-[#31064D] sm:px-8 lg:px-12">
      <div className="mx-auto w-full max-w-5xl">
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

          <section className="pb-4 pt-10 sm:pt-12">
            <p className="mb-3 text-sm font-bold uppercase tracking-[0.22em] text-[#91F0DF]">
              QUIZ BUILDER
            </p>

            <h2 className="brand-font text-4xl font-bold leading-tight text-white sm:text-5xl">
              Create your quiz
            </h2>

            <p className="mt-5 max-w-3xl text-base leading-8 text-white/85 sm:text-lg">
              Bring your questions to life. Add text, attach media, configure options,
              and manage rounds directly with the backend.
            </p>
          </section>
        </header>

        {error && (
          <div className="mb-6 rounded-2xl bg-red-100 p-4 text-red-800 border border-red-300">
            {error}
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-6">
          <section className="rounded-2xl bg-white p-6 shadow-xl sm:p-8">
            <label htmlFor="quiz-title" className="mb-2 block font-bold">
              Quiz title *
            </label>
            <input
              id="quiz-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="e.g. Science & Technology Quiz"
              required
              className="w-full rounded-xl border border-gray-300 px-4 py-3 outline-none focus:ring-2 focus:ring-purple-300"
            />

            <label htmlFor="quiz-desc" className="mt-4 mb-2 block font-bold">
              Description (optional)
            </label>
            <textarea
              id="quiz-desc"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Brief overview of the quiz..."
              rows={2}
              className="w-full rounded-xl border border-gray-300 px-4 py-3 outline-none focus:ring-2 focus:ring-purple-300"
            />
          </section>

          {questions.map((question, questionIndex) => (
            <section
              key={question.id}
              className="rounded-2xl bg-white p-6 shadow-xl sm:p-8"
            >
              <div className="flex items-center justify-between border-b border-gray-200 pb-4">
                <h3 className="font-bold text-lg text-[#31064D]">
                  Question {questionIndex + 1}
                </h3>
                {questions.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeQuestion(questionIndex)}
                    className="text-sm font-semibold text-red-600 hover:text-red-800"
                  >
                    Delete Question
                  </button>
                )}
              </div>

              <div className="mt-4">
                <label className="mb-2 block font-semibold text-sm">
                  Question Text *
                </label>
                <input
                  type="text"
                  value={question.text}
                  onChange={(e) => updateQuestion(questionIndex, "text", e.target.value)}
                  placeholder="Enter the question text"
                  required
                  className="w-full rounded-xl border border-gray-300 px-4 py-2.5 outline-none focus:ring-2 focus:ring-purple-300"
                />
              </div>

              <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-2 block font-semibold text-sm">
                    Time Limit (seconds)
                  </label>
                  <input
                    type="number"
                    min={5}
                    max={300}
                    value={question.duration}
                    onChange={(e) => updateQuestion(questionIndex, "duration", Number(e.target.value))}
                    className="w-full rounded-xl border border-gray-300 px-4 py-2 outline-none focus:ring-2 focus:ring-purple-300"
                  />
                </div>
                <div>
                  <label className="mb-2 block font-semibold text-sm">
                    Points
                  </label>
                  <input
                    type="number"
                    min={0}
                    max={10000}
                    value={question.points}
                    onChange={(e) => updateQuestion(questionIndex, "points", Number(e.target.value))}
                    className="w-full rounded-xl border border-gray-300 px-4 py-2 outline-none focus:ring-2 focus:ring-purple-300"
                  />
                </div>
              </div>

              <div className="mt-4">
                <label className="mb-2 block font-semibold text-sm">
                  Attach Media (image, audio, or video - optional)
                </label>
                <input
                  type="file"
                  accept="image/*,audio/*,video/*"
                  onChange={(e) => handleFileChange(questionIndex, e.target.files?.[0] || null)}
                  className="w-full rounded-xl border border-gray-300 p-2 text-sm text-gray-700 file:mr-4 file:rounded-lg file:border-0 file:bg-[#EDE4F5] file:px-4 file:py-2 file:font-semibold file:text-[#31064D] hover:file:bg-[#DDD0EB]"
                />
                {question.mediaPreview && (
                  <div className="mt-2">
                    <p className="text-xs text-gray-500 mb-1">Preview:</p>
                    <img
                      src={question.mediaPreview}
                      alt="Question media preview"
                      className="max-h-40 rounded-lg border object-contain"
                    />
                  </div>
                )}
              </div>

              <div className="mt-6">
                <p className="mb-3 font-semibold text-sm">
                  Answer Options (Select the radio button for the correct answer) *
                </p>
                <div className="space-y-3">
                  {question.options.map((option, optIdx) => (
                    <div key={optIdx} className="flex items-center gap-3">
                      <input
                        type="radio"
                        id={`q${questionIndex}-opt${optIdx}`}
                        name={`correctAnswer-${questionIndex}`}
                        checked={Number(question.correctAnswer) === optIdx}
                        onChange={() => updateQuestion(questionIndex, "correctAnswer", optIdx)}
                        className="h-5 w-5 accent-[#31064D]"
                      />
                      <span className="font-bold text-sm w-6">
                        {String.fromCharCode(65 + optIdx)}:
                      </span>
                      <input
                        type="text"
                        value={option}
                        onChange={(e) => updateOption(questionIndex, optIdx, e.target.value)}
                        placeholder={`Option ${String.fromCharCode(65 + optIdx)}`}
                        required
                        className="flex-1 rounded-xl border border-gray-300 px-4 py-2 outline-none focus:ring-2 focus:ring-purple-300"
                      />
                    </div>
                  ))}
                </div>
              </div>
            </section>
          ))}

          <div className="flex flex-wrap items-center justify-between gap-4 pt-4">
            <button
              type="button"
              onClick={addQuestion}
              className="rounded-xl border border-[#31064D] px-6 py-3 font-bold text-[#31064D] transition hover:bg-[#EDE4F5]"
            >
              + ADD QUESTION
            </button>

            <div className="flex gap-4">
              <button
                type="button"
                onClick={handleCancel}
                className="rounded-xl border border-white/40 px-6 py-3 font-bold text-white transition hover:bg-white/10"
              >
                CANCEL
              </button>

              <button
                type="submit"
                disabled={submitting}
                className="rounded-xl bg-[#91F0DF] px-8 py-3 font-bold text-[#31064D] transition hover:brightness-105 disabled:opacity-50"
              >
                {submitting ? "SAVING QUIZ..." : "SAVE QUIZ"}
              </button>
            </div>
          </div>
        </form>
      </div>
    </main>
  );
}

export default CreateQuizPage;
