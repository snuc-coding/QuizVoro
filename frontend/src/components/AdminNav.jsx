
import { useNavigate } from "react-router-dom";
import { clearAdminToken } from "../services/api";

function AdminNav() {
  const navigate = useNavigate();

  const navItems = [
    {
      label: "CREATE",
      path: "/admin/create",
      color: "bg-[#C51E50] text-white",
      shadow: "shadow-[0_4px_14px_rgba(197,30,80,0.25)]",
    },
    {
      label: "PRESENT",
      path: "/admin/quizzes",
      color: "bg-[#E6D99D] text-[#321044]",
      shadow: "shadow-[0_4px_14px_rgba(230,217,157,0.2)]",
    },
  ];

  function handleLogout() {
    clearAdminToken();
    sessionStorage.removeItem("asterisSelectedQuizId");
    navigate("/", { replace: true });
  }

  const buttonBase =
    "min-w-[110px] rounded-xl px-5 py-3 text-sm font-extrabold tracking-wide " +
    "transition-all duration-200 ease-out hover:-translate-y-1 " +
    "hover:brightness-110 active:translate-y-0 active:scale-95 " +
    "focus-visible:outline-2 focus-visible:outline-offset-4 " +
    "focus-visible:outline-[#D8B4FE]";

  return (
    <header className="mb-8 flex w-full flex-wrap items-center justify-between gap-5 border-b border-white/15 pb-5">

      {/* BRAND */}
      <button
        type="button"
        onClick={() => navigate("/admin/dashboard")}
        className="brand-font text-4xl font-bold text-white transition hover:scale-105 sm:text-5xl"
        aria-label="Asteris admin dashboard"
      >
        Asteris
      </button>

      {/* NAVIGATION BUTTONS */}
      <nav
        aria-label="Admin navigation"
        className="flex flex-wrap items-center justify-center gap-3"
      >
        {navItems.map((item) => (
          <button
            key={item.label}
            type="button"
            onClick={() => navigate(item.path)}
            className={`${buttonBase} ${item.color} ${item.shadow}`}
          >
            {item.label}
          </button>
        ))}

        {/* LOGOUT */}
        <button
          type="button"
          onClick={handleLogout}
          className={`${buttonBase} border border-white/40 bg-white/5 text-white hover:bg-white/15`}
        >
          LOGOUT
        </button>
      </nav>
    </header>
  );
}

export default AdminNav;
