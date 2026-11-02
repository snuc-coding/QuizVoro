
import { useNavigate, useLocation } from "react-router-dom";
import { getAdminUsername, clearAdminToken } from "../services/api";

function AdminDashboardPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const username = getAdminUsername() || "Admin";

  function handleLogout() {
    clearAdminToken();
    sessionStorage.removeItem("asterisSelectedQuizId");
    navigate("/", { replace: true });
  }

  const navItems = [
    {
      label: "JOIN",
      path: "/",
      style: "bg-white text-[#321044] hover:bg-gray-100",
    },
    {
      label: "CREATE",
      path: "/admin/create",
      style: "bg-[#C51E50] text-white hover:bg-[#D6295D]",
    },
    {
      label: "PRESENT",
      path: "/admin/quizzes",
      style: "bg-[#E6D99D] text-[#321044] hover:bg-[#F0E4AE]",
    },
  ];

  return (
    <main className="quiz-background min-h-screen px-5 py-6 sm:px-8 lg:px-12">
      <div className="mx-auto w-full max-w-6xl">

        {/* HEADER */}
        <header className="flex flex-col gap-5 border-b border-white/20 pb-6 sm:flex-row sm:items-center sm:justify-between">

          {/* ASTERIS LOGO */}
          <button
            type="button"
            onClick={() => navigate("/admin/dashboard")}
            className="brand-font self-start text-4xl font-bold leading-tight text-white sm:text-5xl"
            aria-label="Asteris admin dashboard"
          >
            Asteris!
          </button>

          {/* NAVIGATION */}
          <nav
            aria-label="Admin navigation"
            className="flex flex-wrap items-center gap-2 sm:gap-3"
          >
            {navItems.map((item) => {
              const isActive = location.pathname === item.path;

              return (
                <button
                  key={item.label}
                  type="button"
                  onClick={() => navigate(item.path)}
                  aria-current={isActive ? "page" : undefined}
                  className={`
                    nav-font min-h-[46px] rounded-2xl px-5 py-3
                    font-bold tracking-wide
                    transition duration-200
                    hover:-translate-y-0.5
                    ${item.style}
                    ${isActive ? "shadow-lg ring-2 ring-white/30" : ""}
                  `}
                >
                  {item.label}
                </button>
              );
            })}

            {/* LOGOUT */}
            <button
              type="button"
              onClick={handleLogout}
              className="nav-font min-h-[46px] rounded-2xl border border-white/40 px-5 py-3 font-bold text-white transition hover:bg-white/10"
            >
              LOGOUT
            </button>
          </nav>
        </header>

        {/* DASHBOARD CONTENT */}
        <section className="py-12 sm:py-16">

          <p className="mb-3 text-sm font-bold uppercase tracking-[0.25em] text-[#91F0DF]">
            ADMIN WORKSPACE
          </p>

          <h1 className="brand-font text-4xl font-bold leading-tight text-white sm:text-5xl lg:text-6xl">
            Welcome, {username}!
          </h1>

          <p className="mt-5 max-w-2xl text-base leading-7 text-white/85 sm:text-lg">
            Welcome to your Asteris control center. Create quizzes,
            manage saved quizzes, and host live quiz events using
            the navigation above.
          </p>

          {/* QUICK ACTIONS */}
          <div className="mt-10 grid gap-5 sm:grid-cols-2">

            <button
              type="button"
              onClick={() => navigate("/admin/create")}
              className="rounded-3xl bg-[#C51E50] p-7 text-left text-white shadow-xl transition duration-200 hover:-translate-y-1 hover:bg-[#D6295D]"
            >
              <span className="nav-font text-2xl font-bold">
                CREATE QUIZ
              </span>
              <p className="mt-3 text-sm leading-6 text-white/90">
                Build a new quiz and add questions for your next
                Asteris event.
              </p>
              <span className="mt-5 inline-block font-bold">
                GET STARTED →
              </span>
            </button>

            <button
              type="button"
              onClick={() => navigate("/admin/quizzes")}
              className="rounded-3xl bg-[#E6D99D] p-7 text-left text-[#321044] shadow-xl transition duration-200 hover:-translate-y-1 hover:bg-[#F0E4AE]"
            >
              <span className="nav-font text-2xl font-bold">
                PRESENT QUIZ
              </span>
              <p className="mt-3 text-sm leading-6 text-[#321044]/80">
                View your saved quizzes and get ready to host
                a live game.
              </p>
              <span className="mt-5 inline-block font-bold">
                VIEW QUIZZES →
              </span>
            </button>

          </div>
        </section>
      </div>
    </main>
  );
}

export default AdminDashboardPage;
