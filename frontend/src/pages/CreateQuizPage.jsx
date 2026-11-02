
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
            console.warn(
              `Media upload warning for question ${i + 1}:`,
              uploadErr
            );
          }
        }
      }

      alert("Quiz successfully created and saved to the backend!");
      navigate("/admin/quizzes", { replace: true });
    } catch (err) {
      console.error("Failed to save quiz to backend:", err);
      setError(
        err.message ||
          "Failed to save quiz to backend. Please check connectivity."
      );
    } finally {
      setSubmitting(false);
    }
  }

  function handleCancel() {
    navigate("/admin/dashboard");
  }

  const inputStyle =
    "w-full rounded-xl border border-[#DED9E5] bg-[#F4F2F7] px-4 py-3 text-[#321044] outline-none transition placeholder:text-gray-400 focus:border-[#7950A8] focus:ring-2 focus:ring-purple-100";

  return (
    <main className="quiz-background min-h-screen px-5 py-8 sm:px-8 lg:px-12">
      <div className="mx-auto w-full max-w-5xl">

        {/* HEADER */}
        <header className="mb-10">
          <div className="flex min-h-[72px] items-center justify-between gap-4 border-b border-white/20 pb-6">

            <button
              type="button"
              onClick={() => navigate("/admin/dashboard")}
              className="brand-font text-4xl font-bold leading-tight text-white sm:text-5xl"
              aria-label="Go to admin dashboard"
            >
              Asteris!
            </button>

            <button
              type="button"
              onClick={handleLogout}
              className="nav-font shrink-0 rounded-xl border border-white/40 px-5 py-3 font-bold text-white transition hover:bg-white/10"
            >
              LOGOUT
            </button>
          </div>

          {/* PAGE INTRO */}
          <section className="pb-4 pt-10 sm:pt-12">
            <p className="mb-3 text-sm font-bold uppercase tracking-[0.22em] text-[#E6D99D]">
              ASTERIS • QUIZ BUILDER
            </p>

            <h1 className="brand-font text-4xl font-bold leading-tight text-white sm:text-5xl">
              Create your quiz
            </h1>

            <p className="mt-4 max-w-3xl text-base leading-8 text-white/85 sm:text-lg">
              Bring your questions to life. Add text, attach media,
              configure your answer options, and prepare for your next
              Asteris game.
            </p>
          </section>
        </header>

        {/* ERROR MESSAGE */}
        {error && (
          <div
            role="alert"
            className="mb-6 rounded-2xl border border-red-200 bg-red-50 p-4 font-medium text-red-700 shadow-sm"
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-7">

          {/* QUIZ INFORMATION */}
          <section className="rounded-3xl border border-white/50 bg-white p-6 shadow-xl sm:p-8">

            <div className="mb-6 flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#F5E9EF] text-lg font-bold text-[#C51E50]">
                01
              </div>

              <div>
                <h2 className="nav-font text-xl font-bold text-[#321044]">
                  Quiz Information
                </h2>
                <p className="text-sm text-gray-500">
                  Give your quiz a name and description.
                </p>
              </div>
            </div>

            <label htmlFor="quiz-title" className="mb-2 block text-sm font-bold text-[#321044]">
              Quiz Title *
            </label>

            <input
              id="quiz-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="e.g. Science & Technology Quiz"
              required
              className={inputStyle}
            />

            <label htmlFor="quiz-desc" className="mb-2 mt-5 block text-sm font-bold text-[#321044]">
              Description (optional)
            </label>

            <textarea
              id="quiz-desc"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Brief overview of the quiz..."
              rows={3}
              className={`${inputStyle} resize-y`}
            />
          </section>

          {/* QUESTIONS */}
          {questions.map((question, questionIndex) => (
            <section
              key={question.id}
              className="overflow-hidden rounded-3xl border border-white/50 bg-white shadow-xl"
            >

              {/* QUESTION HEADER */}
              <div className="flex items-center justify-between gap-3 border-b border-[#EAE6EF] bg-[#F8F6FA] px-6 py-5 sm:px-8">
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#321044] text-lg font-bold text-white">
                    {String(questionIndex + 1).padStart(2, "0")}
                  </div>

                  <div>
                    <h3 className="nav-font text-lg font-bold text-[#321044]">
                      Question {questionIndex + 1}
                    </h3>
                    <p className="text-xs text-gray-500">
                      Multiple choice question
                    </p>
                  </div>
                </div>

                {questions.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeQuestion(questionIndex)}
                    className="rounded-xl px-3 py-2 text-sm font-bold text-red-600 transition hover:bg-red-50"
                  >
                    DELETE
                  </button>
                )}
              </div>

              <div className="space-y-6 p-6 sm:p-8">

                {/* QUESTION TEXT */}
                <div>
                  <label className="mb-2 block text-sm font-bold text-[#321044]">
                    Question Text *
                  </label>

                  <input
                    type="text"
                    value={question.text}
                    onChange={(e) =>
                      updateQuestion(questionIndex, "text", e.target.value)
                    }
                    placeholder="Enter your question here..."
                    required
                    className={inputStyle}
                  />
                </div>

                {/* TIME AND POINTS */}
                <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-sm font-bold text-[#321044]">
                      Time Limit (seconds)
                    </label>

                    <input
                      type="number"
                      min={5}
                      max={300}
                      value={question.duration}
                      onChange={(e) =>
                        updateQuestion(
                          questionIndex,
                          "duration",
                          Number(e.target.value)
                        )
                      }
                      className={inputStyle}
                    />
                  </div>

                  <div>
                    <label className="mb-2 block text-sm font-bold text-[#321044]">
                      Points
                    </label>

                    <input
                      type="number"
                      min={0}
                      max={10000}
                      value={question.points}
                      onChange={(e) =>
                        updateQuestion(
                          questionIndex,
                          "points",
                          Number(e.target.value)
                        )
                      }
                      className={inputStyle}
                    />
                  </div>
                </div>

                {/* MEDIA UPLOAD */}
                <div className="rounded-2xl border border-dashed border-[#C9B9D8] bg-[#F8F5FB] p-5">
                  <label className="mb-3 block text-sm font-bold text-[#321044]">
                    Attach Media
                  </label>

                  <p className="mb-4 text-xs text-gray-500">
                    Optional: Add an image, audio clip, or video to your question.
                  </p>

                  <input
                    type="file"
                    accept="image/*,audio/*,video/*"
                    onChange={(e) =>
                      handleFileChange(
                        questionIndex,
                        e.target.files?.[0] || null
                      )
                    }
                    className="w-full rounded-xl border border-[#DED9E5] bg-white p-3 text-sm text-gray-700 file:mr-4 file:rounded-lg file:border-0 file:bg-[#321044] file:px-4 file:py-2 file:font-semibold file:text-white hover:file:bg-[#49205C]"
                  />

                  {question.mediaPreview && (
                    <div className="mt-4">
                      <p className="mb-2 text-xs font-bold text-gray-500">
                        MEDIA PREVIEW
                      </p>

                      <img
                        src={question.mediaPreview}
                        alt="Question media preview"
                        className="max-h-48 rounded-xl border border-[#DED9E5] object-contain"
                      />
                    </div>
                  )}
                </div>

                {/* ANSWER OPTIONS */}
                <div>
                  <div className="mb-4">
                    <h4 className="font-bold text-[#321044]">
                      Answer Options *
                    </h4>
                    <p className="mt-1 text-xs text-gray-500">
                      Select the radio button beside the correct answer.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    {question.options.map((option, optIdx) => {
                      const optionColors = [
                        "border-[#E9B6C5] bg-[#FFF5F7]",
                        "border-[#E9DFA8] bg-[#FFFCEF]",
                        "border-[#B9D4F4] bg-[#F3F8FF]",
                        "border-[#B8E4D8] bg-[#F1FBF7]",
                      ];

                      return (
                        <div
                          key={optIdx}
                          className={`flex items-center gap-3 rounded-2xl border p-3 transition focus-within:ring-2 focus-within:ring-purple-200 ${optionColors[optIdx]}`}
                        >
                          <input
                            type="radio"
                            id={`q${questionIndex}-opt${optIdx}`}
                            name={`correctAnswer-${questionIndex}`}
                            checked={Number(question.correctAnswer) === optIdx}
                            onChange={() =>
                              updateQuestion(
                                questionIndex,
                                "correctAnswer",
                                optIdx
                              )
                            }
                            className="h-5 w-5 accent-[#321044]"
                          />

                          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white text-sm font-bold text-[#321044] shadow-sm">
                            {String.fromCharCode(65 + optIdx)}
                          </span>

                          <input
                            type="text"
                            value={option}
                            onChange={(e) =>
                              updateOption(
                                questionIndex,
                                optIdx,
                                e.target.value
                              )
                            }
                            placeholder={`Option ${String.fromCharCode(65 + optIdx)}`}
                            required
                            className="min-w-0 flex-1 bg-transparent text-sm font-medium text-[#321044] outline-none placeholder:text-gray-400"
                          />
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* CORRECT ANSWER INDICATOR */}
                <div className="rounded-xl bg-[#F1FBF7] px-4 py-3 text-sm text-[#24785B]">
                  <span className="font-bold">Correct answer: </span>
                  Option {String.fromCharCode(65 + Number(question.correctAnswer))}
                </div>

              </div>
            </section>
          ))}

          {/* ADD QUESTION */}
          <button
            type="button"
            onClick={addQuestion}
            className="w-full rounded-2xl border-2 border-dashed border-white/60 bg-white/10 px-6 py-5 font-bold text-white transition hover:bg-white/20"
          >
            + ADD ANOTHER QUESTION
          </button>

          {/* BOTTOM ACTIONS */}
          <div className="flex flex-col-reverse justify-between gap-4 border-t border-white/20 pt-6 sm:flex-row sm:items-center">

            <button
              type="button"
              onClick={handleCancel}
              className="rounded-xl border border-white/40 px-7 py-3.5 font-bold text-white transition hover:bg-white/10"
            >
              CANCEL
            </button>

            <button
              type="submit"
              disabled={submitting}
              className="nav-font rounded-xl bg-[#C51E50] px-9 py-4 font-bold text-white shadow-lg transition hover:bg-[#D6295D] hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? "SAVING QUIZ..." : "SAVE QUIZ →"}
            </button>

          </div>
        </form>
      </div>
    </main>
  );
}

export default CreateQuizPage;
