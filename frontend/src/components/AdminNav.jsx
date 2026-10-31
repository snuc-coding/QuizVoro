import { useNavigate } from "react-router-dom";
import { clearAdminToken } from "../services/api";

function AdminNav() {
  const navigate = useNavigate();

  const navItems = [
    {
      label: "CREATE",
      path: "/admin/create",
      color: "bg-[#C51E50] text-white",
    },
    {
      label: "PRESENT",
      path: "/admin/quizzes",
      color: "bg-[#E6D99D] text-[#321044]",
    },
  ];

  function handleLogout() {
    clearAdminToken();
    sessionStorage.removeItem("asterisSelectedQuizId");
    navigate("/", { replace: true });
  }

  return (
    <header className="mb-8 flex w-full flex-wrap items-center justify-between gap-5 border-b border-white/20 pb-5">
      <button
        type="button"
        onClick={() => navigate("/admin/dashboard")}
        className="brand-font text-4xl font-bold text-white sm:text-5xl"
        aria-label="Asteris admin dashboard"
      >
        Asteris
      </button>

      <nav
        aria-label="Admin navigation"
        className="flex flex-wrap items-center gap-2"
      >
        {navItems.map((item) => (
          <button
            key={item.label}
            type="button"
            onClick={() => navigate(item.path)}
            className={`rounded-xl px-4 py-3 font-bold transition hover:-translate-y-0.5 hover:brightness-105 ${item.color}`}
          >
            {item.label}
          </button>
        ))}

        <button
          type="button"
          onClick={handleLogout}
          className="rounded-xl border border-white/40 px-4 py-3 font-bold text-white transition hover:bg-white/10"
        >
          LOGOUT
        </button>
      </nav>
    </header>
  );
}

export default AdminNav;
