
import { useNavigate, useLocation } from "react-router-dom";

function AdminNav() {
  const navigate = useNavigate();
  const location = useLocation();

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
    {
      label: "JOIN",
      path: "/",
      color: "bg-[#91F0DF] text-[#17232A]",
    },
  ];

  function handleLogout() {
    sessionStorage.removeItem("asterisAdminLoggedIn");
    navigate("/", { replace: true });
  }

  return (
    <header className="mb-8 flex w-full flex-wrap items-center justify-between gap-5 border-b border-white/20 pb-5">
      <button
        type="button"
        onClick={() => navigate("/admin/create")}
        className="brand-font text-4xl font-bold text-white sm:text-5xl"
      >
        Asteris
      </button>

      <nav className="flex flex-wrap items-center gap-2">
        {navItems.map((item) => (
          <button
            key={item.label}
            type="button"
            onClick={() => navigate(item.path)}
            aria-current={
              location.pathname === item.path ? "page" : undefined
            }
            className={`rounded-xl px-4 py-3 font-bold transition hover:-translate-y-0.5 hover:brightness-105 ${item.color}`}
          >
            {item.label}
          </button>
        ))}

        
        <button
          type="button"
          onClick={handleLogout}
          className="rounded-xl border border-white/50 px-4 py-3 font-bold text-white transition hover:bg-white/10"
        >
          LOGOUT
        </button>
      </nav>
    </header>
  );
}

export default AdminNav;
