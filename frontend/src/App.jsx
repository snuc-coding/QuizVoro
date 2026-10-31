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

  // Participant join-flow state for top-bar or direct routes
  const [pin, setPin] = useState("");
  const [nickname, setNickname] = useState("");
  const [showLoginPrompt, setShowLoginPrompt] = useState(false);
  const [pendingAction, setPendingAction] = useState("create");

  const loggedIn = isAdminAuthenticated();

  function handleTabChange(tab) {
    if (tab === "JOIN") {
      setPin("");
      setNickname("");
      navigate("/");
      return;
    }

    if (loggedIn) {
      navigate(tab === "CREATE" ? "/admin/create" : "/admin/quizzes");
      return;
    }

    setPendingAction(tab.toLowerCase());
    setShowLoginPrompt(true);
  }

  function handleConfirmLogin() {
    setShowLoginPrompt(false);
    navigate(`/admin/login?mode=${pendingAction}`, {
      state: { fromPrompt: true },
    });
  }

  function handleContinue(name) {
    setNickname(name);
    navigate("/lobby");
  }

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
        <Route path="/admin/login" element={<AdminLoginPage />} />
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
        <Route path="/stage" element={<ProjectorPage />} />
        <Route path="/game/:gameId" element={<QuestionScreen />} />
      </Routes>
    );
  }

  return (
    <div className="quiz-background min-h-screen text-white">
      {/* Top Navbar */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-white/10">
        <button
          onClick={() => navigate("/")}
          className="brand-font text-3xl font-extrabold tracking-wider"
        >
          Asteris
        </button>

        <nav className="flex items-center gap-2">
          <button
            onClick={() => handleTabChange("JOIN")}
            className={`rounded-xl px-4 py-2 font-bold text-sm transition ${
              activeTab === "JOIN"
                ? "bg-white text-[#31064D]"
                : "text-white/80 hover:bg-white/10"
            }`}
          >
            JOIN
          </button>
          <button
            onClick={() => handleTabChange("CREATE")}
            className={`rounded-xl px-4 py-2 font-bold text-sm transition ${
              activeTab === "CREATE"
                ? "bg-[#C51E50] text-white"
                : "text-white/80 hover:bg-white/10"
            }`}
          >
            CREATE
          </button>
          <button
            onClick={() => handleTabChange("PRESENT")}
            className={`rounded-xl px-4 py-2 font-bold text-sm transition ${
              activeTab === "PRESENT"
                ? "bg-[#E6D99D] text-[#31064D]"
                : "text-white/80 hover:bg-white/10"
            }`}
          >
            PRESENT
          </button>
        </nav>
      </header>

      {/* Main Routes */}
      <main className="flex min-h-[calc(100vh-80px)] items-center justify-center p-4">
        <Routes>
          <Route path="/" element={<JoinPage />} />
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
          <Route path="/join-flow" element={<JoinFlow />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      {/* Login Prompt Modal */}
      {showLoginPrompt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-sm rounded-3xl bg-white p-7 text-[#31064D] shadow-2xl text-center">
            <h3 className="brand-font text-2xl font-bold">Admin Sign In Required</h3>
            <p className="mt-2 text-sm text-gray-600">
              You must sign in as an administrator to {pendingAction} quizzes.
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
                className="w-full rounded-xl border border-gray-300 py-2.5 font-semibold text-gray-600 hover:bg-gray-50"
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
