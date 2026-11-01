
import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { authApi } from "../services/api";

function AdminLoginPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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
    <main className="min-h-screen w-full bg-gradient-to-br from-[#210B32] via-[#351047] to-[#1B0928] px-5 py-6 sm:px-10">

      <div className="mx-auto w-full max-w-6xl">

        {/* HEADER */}
        <header className="flex min-h-[64px] items-center justify-between border-b border-white/10 pb-4">

          <button
            type="button"
            onClick={() => navigate("/")}
            className="brand-font text-3xl font-bold text-white sm:text-4xl"
            aria-label="Asteris home"
          >
            Asteris!
          </button>

          <button
            type="button"
            onClick={() => navigate("/")}
            className="rounded-xl border border-white/30 px-5 py-2.5 text-sm font-bold text-white transition hover:bg-white/10"
          >
            CANCEL
          </button>

        </header>

        {/* LOGIN CARD */}
        <section className="mx-auto mt-10 flex w-full max-w-md flex-col justify-center rounded-3xl border border-white/20 bg-[#F0EFF2] px-6 py-8 text-[#321044] shadow-2xl sm:mt-12 sm:px-9 sm:py-9">

          {/* TITLE */}
          <div className="mb-7 text-center">

            <p className="text-xs font-bold uppercase tracking-[0.25em] text-[#9D315A]">
              ASTERIS ADMIN
            </p>

            <h1 className="brand-font mt-2 text-3xl font-bold sm:text-4xl">
              Admin Login
            </h1>

            <p className="mt-4 text-sm leading-6 text-gray-600">
              Sign in to access your dashboard, create quizzes,
              and manage live presentations.
            </p>

          </div>

          {/* LOGIN FORM */}
          <form onSubmit={handleLogin} className="space-y-5">

            {/* USERNAME */}
            <div>
              <label
                htmlFor="username"
                className="mb-2 block text-sm font-bold text-[#321044]"
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
                className="min-h-[50px] w-full rounded-xl border border-[#D5D3DC] bg-[#E8ECF5] px-4 text-sm text-[#321044] outline-none transition placeholder:text-gray-500 focus:border-[#7950A8] focus:ring-2 focus:ring-purple-200 disabled:opacity-60"
              />
            </div>

            {/* PASSWORD */}
            <div>
              <label
                htmlFor="password"
                className="mb-2 block text-sm font-bold text-[#321044]"
              >
                Password
              </label>

              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Enter password"
                  required
                  disabled={loading}
                  className="min-h-[50px] w-full rounded-xl border border-[#D5D3DC] bg-[#E8ECF5] px-4 pr-16 text-sm text-[#321044] outline-none transition placeholder:text-gray-500 focus:border-[#7950A8] focus:ring-2 focus:ring-purple-200 disabled:opacity-60"
                />

                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  disabled={loading}
                  className="absolute inset-y-0 right-3 text-xs font-bold text-[#5B456E] hover:text-[#321044]"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? "HIDE" : "SHOW"}
                </button>
              </div>
            </div>

            {/* ERROR */}
            {error && (
              <p
                role="alert"
                className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-600"
              >
                {error}
              </p>
            )}

            {/* LOGIN BUTTON */}
            <button
              type="submit"
              disabled={loading}
              className="brand-font min-h-[54px] w-full rounded-xl bg-[#31064D] py-3.5 text-base font-bold text-white shadow-md transition duration-200 hover:bg-[#49205C] hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? "SIGNING IN..." : "LOGIN"}
            </button>

          </form>
        </section>

      </div>
    </main>
  );
}

export default AdminLoginPage;
