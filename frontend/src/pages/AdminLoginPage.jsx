import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { authApi } from "../services/api";

function AdminLoginPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin(event) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      await authApi.login(username.trim(), password);

      const params = new URLSearchParams(location.search);
      const mode = params.get("mode");

      if (mode === "create") {
        navigate("/admin/create", { replace: true });
      } else if (mode === "present") {
        navigate("/admin/quizzes", { replace: true });
      } else {
        navigate("/admin/dashboard", { replace: true });
      }
    } catch (err) {
      console.error("Admin login failed:", err);
      setError(err.message || "Invalid username or password.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen px-5 py-8 sm:px-8 lg:px-12">
      <div className="mx-auto w-full max-w-5xl">
        <header className="mb-10 flex min-h-[72px] items-center justify-between gap-4 border-b border-white/20 pb-5">
          <button
            type="button"
            onClick={() => navigate("/")}
            className="brand-font text-4xl font-bold leading-tight text-white sm:text-5xl"
          >
            Asteris
          </button>

          <button
            type="button"
            onClick={() => navigate("/")}
            className="rounded-xl border border-white/40 px-5 py-2.5 font-semibold text-white transition hover:bg-white/10"
          >
            CANCEL
          </button>
        </header>

        <section className="mx-auto mt-12 w-full max-w-lg rounded-3xl bg-white px-7 py-9 text-[#31064D] shadow-2xl sm:px-10 sm:py-10">
          <div className="mb-8 text-center">
            <p className="text-sm font-bold uppercase tracking-[0.22em] text-[#C51E50]">
              ASTERIS ADMIN
            </p>

            <h1 className="brand-font mt-3 text-3xl font-bold sm:text-4xl">
              Admin Login
            </h1>

            <p className="mt-3 text-base leading-6 text-gray-600">
              Sign in to access your dashboard, create quizzes,
              and manage live presentations.
            </p>
          </div>

          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label
                htmlFor="username"
                className="mb-2 block font-semibold"
              >
                Username
              </label>

              <input
                id="username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="Enter username"
                required
                disabled={loading}
                className="w-full rounded-xl border border-gray-300 bg-[#F7F5FC] px-4 py-3 outline-none transition focus:border-[#31064D] focus:ring-2 focus:ring-purple-200"
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="mb-2 block font-semibold"
              >
                Password
              </label>

              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter password"
                required
                disabled={loading}
                className="w-full rounded-xl border border-gray-300 bg-[#F7F5FC] px-4 py-3 outline-none transition focus:border-[#31064D] focus:ring-2 focus:ring-purple-200"
              />
            </div>

            {error && (
              <p
                role="alert"
                className="rounded-xl bg-red-50 px-4 py-3 text-sm font-medium text-red-600 border border-red-200"
              >
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="brand-font w-full rounded-xl bg-[#31064D] py-3.5 text-lg font-bold text-white transition hover:bg-[#49205C] disabled:opacity-50"
            >
              {loading ? "SIGNING IN..." : "SIGN IN"}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}

export default AdminLoginPage;
