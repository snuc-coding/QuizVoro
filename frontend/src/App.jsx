
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
import PresentationControlPage from "./pages/PresentationControlPage";

function isAdminLoggedIn() {
  return sessionStorage.getItem("asterisAdminLoggedIn") === "true";
}

// Protect admin-only pages.
function AdminRoute({ children }) {
  return isAdminLoggedIn() ? (
    children
  ) : (
    <Navigate to="/admin/login" replace />
  );
}

function App() {
  const navigate = useNavigate();
  const location = useLocation();

  // State for the original join flow.
  const [pin, setPin] = useState("");
  const [nickname, setNickname] = useState("");

  // State for the admin login prompt.
  const [showLoginPrompt, setShowLoginPrompt] = useState(false);
  const [pendingAction, setPendingAction] = useState("create");

  const loggedIn = isAdminLoggedIn();

  function handleTabChange(tab) {
    if (tab === "JOIN") {
      setPin("");
      setNickname("");
      navigate("/");
      return;
    }

    if (loggedIn) {
      navigate("/admin/dashboard");
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

  // Original join flow: PIN -> nickname -> lobby.
  function handleJoin(gamePin) {
  setPin(gamePin);
  navigate("/nickname");
}

function handleContinue(name) {
  setNickname(name);
  navigate("/lobby");
}

  function handleLogout() {
    sessionStorage.removeItem("asterisAdminLoggedIn");
    sessionStorage.removeItem("asterisAdminUsername");
    sessionStorage.removeItem("asterisSelectedQuizId");

    setPin("");
    setNickname("");
    setShowLoginPrompt(false);

    navigate("/", { replace: true });
  }

  const activeTab =
    location.pathname === "/"
      ? "JOIN"
      : location.pathname.startsWith("/admin/create")
      ? "CREATE"
      : location.pathname === "/admin/quizzes" ||
        location.pathname === "/admin/presentation" ||
        location.pathname === "/stage"
      ? "PRESENT"
      : "";

  const tabs = [
    {
      label: "CREATE",
      color: "bg-[#C51E50] hover:bg-[#D6295D]",
      text: "text-white",
    },
    {
      label: "PRESENT",
      color: "bg-[#E6D99D] hover:bg-[#F0E4AE]",
      text: "text-[#321044]",
    },
    {
      label: "JOIN",
      color: "bg-[#91F0DF] hover:bg-[#ACF7EA]",
      text: "text-[#17232A]",
    },
  ];

  return (
    <div className="quiz-background min-h-screen text-white">
      <Routes>
        {/* Public home and original PIN entry. */}
        <Route
          path="/"
          element={
            loggedIn ? (
              <Navigate to="/admin/dashboard" replace />
            ) : (
              <>
                <header className="relative z-20 flex min-h-[78px] w-full items-center justify-between gap-3 border-b border-white/15 bg-[#260638]/90 px-4 backdrop-blur-md sm:px-8 lg:px-14">
                  <button
                    type="button"
                    onClick={() => navigate("/")}
                    className="brand-font shrink-0 text-3xl leading-none text-white sm:text-4xl"
                    aria-label="Asteris home"
                  >
                    Asteris
                  </button>

                  <nav
                    aria-label="Main navigation"
                    className="flex flex-wrap items-center justify-end gap-2 sm:gap-3"
                  >
                    {tabs.map((tab) => (
                      <button
                        key={tab.label}
                        type="button"
                        aria-current={
                          activeTab === tab.label ? "page" : undefined
                        }
                        onClick={() => handleTabChange(tab.label)}
                        className={`nav-font flex min-h-[44px] items-center justify-center rounded-xl border border-black/10 px-3 py-2 text-sm font-bold transition hover:-translate-y-0.5 hover:brightness-105 sm:min-w-[100px] sm:px-5 sm:text-base ${tab.color} ${tab.text} ${
                          activeTab === tab.label
                            ? "shadow-md ring-2 ring-white/60 ring-offset-2 ring-offset-[#260638]"
                            : "shadow-sm"
                        }`}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </nav>
                </header>

                <main className="relative z-10 flex min-h-[calc(100svh-78px)] items-center justify-center px-4 py-12">
                  <JoinPage onJoin={handleJoin} />
                </main>
              </>
            )
          }
        />

        {/* Original participant nickname page. */}
        <Route
          path="/nickname"
          element={
            <main className="flex min-h-screen w-full items-center justify-center px-4 py-12">
              <NicknamePage
                pin={pin}
                onContinue={handleContinue}
                onBack={() => navigate("/")}
              />
            </main>
          }
        />

        {/* Original participant lobby. */}
        <Route
          path="/lobby"
          element={
            <div className="flex min-h-screen w-full flex-col items-center justify-center gap-4 px-4 py-8">
              <WaitingLobby
                nickname={nickname}
                pin={pin}
                onBack={() => navigate("/nickname")}
              />

              {import.meta.env.DEV && (
                <button
                  type="button"
                  onClick={() => navigate("/question")}
                  className="rounded-xl bg-white px-6 py-3 font-bold text-[#31064D]"
                >
                  TEST QUESTION SCREEN
                </button>
              )}
            </div>
          }
        />

        {/* Participant question screen. */}
        <Route
          path="/question"
          element={<QuestionScreen />}
        />

        {/* QR-based join flow. */}
        <Route
          path="/join"
          element={<JoinFlow />}
        />

        {/* Projector screen. */}
        <Route
          path="/stage"
          element={<ProjectorPage />}
        />

        {/* Admin login. */}
        <Route
          path="/admin/login"
          element={
            loggedIn ? (
              <Navigate to="/admin/dashboard" replace />
            ) : (
              <AdminLoginPage />
            )
          }
        />

        {/* Admin dashboard. */}
        <Route
          path="/admin/dashboard"
          element={
            <AdminRoute>
              <AdminDashboardPage />
            </AdminRoute>
          }
        />

        {/* Create quiz. */}
        <Route
          path="/admin/create"
          element={
            <AdminRoute>
              <CreateQuizPage />
            </AdminRoute>
          }
        />

        <Route
          path="/admin/create/questions"
          element={
            <AdminRoute>
              <CreateQuizPage />
            </AdminRoute>
          }
        />

        {/* Saved quizzes. */}
        <Route
          path="/admin/quizzes"
          element={
            <AdminRoute>
              <QuizManagementPage />
            </AdminRoute>
          }
        />

        {/* Presentation controls. */}
        <Route
          path="/admin/presentation"
          element={
            <AdminRoute>
              <PresentationControlPage />
            </AdminRoute>
          }
        />

        {/* Unknown URLs. */}
        <Route
          path="*"
          element={
            <Navigate
              to={loggedIn ? "/admin/dashboard" : "/"}
              replace
            />
          }
        />
      </Routes>

      {/* Admin login confirmation dialog. */}
      {showLoginPrompt && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 px-4 backdrop-blur-sm"
          onClick={() => setShowLoginPrompt(false)}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="login-prompt-title"
            className="w-full max-w-md rounded-3xl bg-white p-7 text-center text-[#31064D] shadow-2xl sm:p-9"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-purple-100">
              <span className="text-3xl" aria-hidden="true">
                🔐
              </span>
            </div>

            <h2
              id="login-prompt-title"
              className="brand-font text-3xl font-bold"
            >
              Admin Login Required
            </h2>

            <p className="mt-4 leading-7 text-gray-600">
              You need to log in as an admin to{" "}
              {pendingAction === "create"
                ? "create and manage quizzes"
                : "select and present quizzes"}
              .
            </p>

            <p className="mt-2 text-gray-600">
              Would you like to log in now?
            </p>

            <div className="mt-7 flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                onClick={handleConfirmLogin}
                className="flex-1 rounded-xl bg-[#31064D] px-5 py-3 font-bold text-white transition hover:bg-[#49205C]"
              >
                YES, LOGIN
              </button>

              <button
                type="button"
                onClick={() => setShowLoginPrompt(false)}
                className="flex-1 rounded-xl border border-gray-300 px-5 py-3 font-bold text-[#31064D] transition hover:bg-gray-100"
              >
                CANCEL
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

export default App;
