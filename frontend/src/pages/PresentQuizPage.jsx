
function PresentQuizPage({ onSelectQuiz, onBack }) {
  const quizzes = [
    { id: 1, name: 'Java', questions: 2 },
    { id: 2, name: 'Computer Networks', questions: 10 },
    { id: 3, name: 'General Knowledge', questions: 15 },
  ]

  return (
    <div className="quiz-background min-h-screen px-5 py-10 text-white sm:px-10">
      <div className="mx-auto w-full max-w-4xl">
        <p className="nav-font text-xs tracking-[0.3em] text-[#91F0DF]">
          QUIZ HOSTING
        </p>

        <h1 className="brand-font mt-2 text-4xl sm:text-5xl">
          Present a quiz
        </h1>

        <p className="mt-3 max-w-2xl text-sm leading-6 text-purple-100/75">
          Choose a saved quiz to prepare for your live presentation.
          You can review the question count before opening the host dashboard.
        </p>

        <div className="mt-8 space-y-4">
          {quizzes.map((quiz) => (
            <div
              key={quiz.id}
              className="flex flex-col gap-4 rounded-2xl border border-white/15 bg-white/95 p-5 text-[#31064D] shadow-lg sm:flex-row sm:items-center sm:justify-between"
            >
              <div>
                <h2 className="nav-font text-2xl">{quiz.name}</h2>
                <p className="mt-1 text-sm text-gray-600">
                  {quiz.questions}{' '}
                  {quiz.questions === 1 ? 'question' : 'questions'}
                </p>
              </div>

              <button
                type="button"
                onClick={() => onSelectQuiz(quiz)}
                className="nav-font rounded-xl bg-[#31064D] px-6 py-3 text-white transition hover:bg-[#49205C]"
              >
                SELECT QUIZ →
              </button>
            </div>
          ))}
        </div>

        <button
          type="button"
          onClick={onBack}
          className="nav-font mt-6 w-full rounded-xl border border-white/20 bg-white/5 px-5 py-3 text-sm text-white transition hover:bg-white/10"
        >
          ← BACK TO ADMIN DASHBOARD
        </button>
      </div>
    </div>
  )
}

export default PresentQuizPage
