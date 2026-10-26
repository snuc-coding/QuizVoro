
import { useNavigate } from "react-router-dom";

function AdminDashboardPage() {
  const navigate = useNavigate();

  const username =
    sessionStorage.getItem("asterisAdminUsername") || "admin";

  function handleLogout() {
    sessionStorage.removeItem("asterisAdminLoggedIn");
    sessionStorage.removeItem("asterisAdminUsername");
    sessionStorage.removeItem("asterisSelectedQuizId");

    navigate("/", { replace: true });
  }

  const navItems = [
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
    {
      label: "JOIN",
      path: "/",
      style: "bg-[#91F0DF] text-[#17232A] hover:bg-[#ACF7EA]",
    },
  ];

  return (
    <main className="min-h-screen px-5 py-6 sm:px-8 lg:px-12">
      <div className="mx-auto w-full max-w-6xl">
        {/* Dashboard header and navigation */}
        <header className="flex flex-col gap-5 border-b border-white/20 pb-6 sm:flex-row sm:items-center sm:justify-between">
          <button
            type="button"
            onClick={() => navigate("/admin/dashboard")}
            className="brand-font self-start text-4xl font-bold leading-tight text-white sm:text-5xl"
          >
            Asteris
          </button>

          <nav
            aria-label="Admin navigation"
            className="flex flex-wrap items-center gap-2 sm:gap-3"
          >
            {navItems.map((item) => (
              <button
                key={item.label}
                type="button"
                onClick={() => navigate(item.path)}
                className={`nav-font min-h-[46px] rounded-xl px-5 py-3 font-bold transition hover:-translate-y-0.5 ${item.style}`}
              >
                {item.label}
              </button>
            ))}

            <button
              type="button"
              onClick={handleLogout}
              className="nav-font min-h-[46px] rounded-xl border border-white/40 px-5 py-3 font-bold text-white transition hover:bg-white/10"
            >
              LOGOUT
            </button>
          </nav>
        </header>

        {/* Welcome section */}
        <section className="py-12 sm:py-16">
          <p className="mb-3 text-sm font-bold uppercase tracking-[0.25em] text-[#91F0DF]">
            ADMIN WORKSPACE
          </p>

          <h1 className="brand-font text-4xl font-bold leading-tight text-white sm:text-5xl lg:text-6xl">
            Welcome, {username}!
          </h1>

          <p className="mt-5 max-w-2xl text-base leading-7 text-white/85 sm:text-lg">
            Welcome to your Asteris control center. Create quizzes,
            manage saved quizzes, or join a game using the navigation
            above.
          </p>
        </section>
      </div>
    </main>
  );
}

export default AdminDashboardPage;
