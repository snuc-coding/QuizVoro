
import { useState } from "react";
import {
  Routes,
  Route,
  Navigate,
  useNavigate,
  useLocation,
} from "react-router-dom";

import JoinPage from "./pages/JoinPage";
import NicknamePage from "./pages/NicknamePage";
import WaitingLobby from "./components/game/WaitingLobby";
import QuestionScreen from "./pages/QuestionScreen";
import ProjectorPage from "./pages/ProjectorPage";
import JoinFlow from "./pages/JoinFlow";

import AdminLoginPage from "./pages/AdminLoginPage";
import CreateQuizPage from "./pages/CreateQuizPage";
import QuizManagementPage from "./pages/QuizManagementPage";
import AdminDashboardPage from "./pages/AdminDashboardPage";
import HostDashboard from "./pages/HostDashboard";

import { isAdminAuthenticated } from "./services/api";

// Protect admin-only pages
function AdminRoute({ children }) {
  return isAdminAuthenticated() ? (
    children
  ) : (
    <Navigate to="/admin/login" replace />
  );
}

function App() {
  const navigate = useNavigate();
  const location = useLocation();

  // Participant join-flow state
  const [pin, setPin] = useState("");
  const [nickname, setNickname] = useState("");
  const [showLoginPrompt, setShowLoginPrompt] = useState(false);
  const [pendingAction, setPendingAction] = useState("create");

  const loggedIn = isAdminAuthenticated();

  // Navigation handler
  function handleTabChange(tab) {
    if (tab === "JOIN") {
      setPin("");
      setNickname("");
      navigate("/");
      return;
    }

    if (loggedIn) {
      navigate(
        tab === "CREATE" ? "/admin/create" : "/admin/quizzes"
      );
      return;
    }

    setPendingAction(tab.toLowerCase());
    setShowLoginPrompt(true);
  }

  // Login prompt confirmation
  function handleConfirmLogin() {
    setShowLoginPrompt(false);

    navigate(`/admin/login?mode=${pendingAction}`, {
      state: { fromPrompt: true },
    });
  }

  // Nickname continuation
  function handleContinue(name) {
    setNickname(name);
    navigate("/lobby");
  }

  // Active navigation tab
  const activeTab =
    location.pathname === "/"
      ? "JOIN"
      : location.pathname.startsWith("/admin/create")
        ? "CREATE"
        : location.pathname === "/admin/quizzes" ||
            location.pathname === "/admin/presentation" ||
            location.pathname === "/admin/host"
          ? "PRESENT"
          : "";

  // Screens without the public navbar
  const isBareScreen =
    location.pathname === "/admin/login" ||
    location.pathname === "/admin/dashboard" ||
    location.pathname.startsWith("/admin/create") ||
    location.pathname === "/admin/quizzes" ||
    location.pathname.startsWith("/admin/host") ||
    location.pathname === "/stage" ||
    location.pathname.startsWith("/game/");

  if (isBareScreen) {
    return (
      <Routes>
        <Route
          path="/admin/login"
          element={<AdminLoginPage />}
        />

        <Route
          path="/admin/dashboard"
          element={
            <AdminRoute>
              <AdminDashboardPage />
            </AdminRoute>
          }
        />

        <Route
          path="/admin/create"
          element={
            <AdminRoute>
              <CreateQuizPage />
            </AdminRoute>
          }
        />

        <Route
          path="/admin/quizzes"
          element={
            <AdminRoute>
              <QuizManagementPage />
            </AdminRoute>
          }
        />

        <Route
          path="/admin/host"
          element={
            <AdminRoute>
              <HostDashboard />
            </AdminRoute>
          }
        />

        <Route
          path="/stage"
          element={<ProjectorPage />}
        />

        <Route
          path="/game/:gameId"
          element={<QuestionScreen />}
        />
      </Routes>
    );
  }

  return (
    <div className="quiz-background min-h-screen text-white">

      {/* TOP NAVBAR */}
      <header className="sticky top-0 z-40 flex w-full flex-nowrap items-center justify-between gap-2 border-b border-white/15 bg-[#310D40]/95 px-3 py-3 backdrop-blur-md sm:gap-4 sm:px-8">

        {/* ASTERIS LOGO */}
        <button
          type="button"
          onClick={() => navigate("/")}
          className="brand-font shrink-0 whitespace-nowrap text-2xl font-extrabold tracking-wide text-white transition duration-200 hover:scale-105 sm:text-4xl"
          aria-label="Asteris home"
        >
          Asteris
        </button>

        {/* NAVIGATION BUTTONS */}
        <nav
          aria-label="Main navigation"
          className="flex shrink-0 flex-nowrap items-center gap-1.5 sm:gap-3"
        >

          {/* JOIN */}
          <button
            type="button"
            onClick={() => handleTabChange("JOIN")}
            aria-current={
              activeTab === "JOIN" ? "page" : undefined
            }
            className={`nav-font flex min-h-[42px] min-w-0 items-center justify-center whitespace-nowrap rounded-xl border-2 px-3 py-2 text-[11px] font-extrabold tracking-wide text-[#31064D] transition-all duration-200 hover:-translate-y-0.5 hover:brightness-105 active:scale-95 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#91F0DF] sm:min-h-[46px] sm:min-w-[90px] sm:px-5 sm:py-2.5 sm:text-sm ${
              activeTab === "JOIN"
                ? "border-[#91F0DF] bg-[#91F0DF] shadow-[0_0_0_2px_rgba(145,240,223,0.2)]"
                : "border-transparent bg-[#91F0DF]"
            }`}
          >
            JOIN
          </button>

          {/* CREATE */}
          <button
            type="button"
            onClick={() => handleTabChange("CREATE")}
            aria-current={
              activeTab === "CREATE" ? "page" : undefined
            }
            className={`nav-font flex min-h-[42px] min-w-0 items-center justify-center whitespace-nowrap rounded-xl border-2 px-3 py-2 text-[11px] font-extrabold tracking-wide text-white transition-all duration-200 hover:-translate-y-0.5 hover:brightness-110 active:scale-95 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#F4A6BE] sm:min-h-[46px] sm:min-w-[100px] sm:px-5 sm:py-2.5 sm:text-sm ${
              activeTab === "CREATE"
                ? "border-[#F4A6BE] bg-[#C51E50] shadow-[0_0_0_2px_rgba(197,30,80,0.2)]"
                : "border-transparent bg-[#C51E50]"
            }`}
          >
            CREATE
          </button>

          {/* PRESENT */}
          <button
            type="button"
            onClick={() => handleTabChange("PRESENT")}
            aria-current={
              activeTab === "PRESENT" ? "page" : undefined
            }
            className={`nav-font flex min-h-[42px] min-w-0 items-center justify-center whitespace-nowrap rounded-xl border-2 px-3 py-2 text-[11px] font-extrabold tracking-wide text-[#321044] transition-all duration-200 hover:-translate-y-0.5 hover:brightness-105 active:scale-95 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#91F0DF] sm:min-h-[46px] sm:min-w-[110px] sm:px-5 sm:py-2.5 sm:text-sm ${
              activeTab === "PRESENT"
                ? "border-[#91F0DF] bg-[#E6D99D] shadow-[0_0_0_2px_rgba(145,240,223,0.2)]"
                : "border-transparent bg-[#E6D99D]"
            }`}
          >
            PRESENT
          </button>

        </nav>
      </header>

      {/* MAIN ROUTES */}
      <main className="flex min-h-[calc(100vh-80px)] items-center justify-center p-4">
        <Routes>
          <Route
            path="/"
            element={<JoinPage />}
          />

          <Route
            path="/nickname"
            element={
              <NicknamePage
                pin={pin}
                onContinue={handleContinue}
                onBack={() => navigate("/")}
              />
            }
          />

          <Route
            path="/lobby"
            element={
              <WaitingLobby
                pin={pin}
                nickname={nickname}
                onBack={() => navigate("/nickname")}
              />
            }
          />

          <Route
            path="/join-flow"
            element={<JoinFlow />}
          />

          <Route
            path="*"
            element={<Navigate to="/" replace />}
          />
        </Routes>
      </main>

      {/* LOGIN PROMPT MODAL */}
      {showLoginPrompt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-sm rounded-3xl bg-white p-7 text-center text-[#31064D] shadow-2xl">

            <h3 className="brand-font text-2xl font-bold">
              Admin Sign In Required
            </h3>

            <p className="mt-2 text-sm text-gray-600">
              You must sign in as an administrator to{" "}
              {pendingAction} quizzes.
            </p>

            <div className="mt-6 flex flex-col gap-2.5">

              <button
                type="button"
                onClick={handleConfirmLogin}
                className="w-full rounded-xl bg-[#31064D] py-3 font-bold text-white transition hover:bg-[#49205C]"
              >
                SIGN IN
              </button>

              <button
                type="button"
                onClick={() => setShowLoginPrompt(false)}
                className="w-full rounded-xl border border-gray-300 py-2.5 font-semibold text-gray-600 transition hover:bg-gray-50"
              >
                Cancel
              </button>

            </div>
          </div>
        </div>
      )}

    </div>
  );
}

export default App;
