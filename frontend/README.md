# Asteris — Live Quiz Platform

Asteris is a real-time, interactive quiz platform inspired by Kahoot. It is designed for hosting live quiz events, allowing participants to join using a Game PIN or QR code, answer multiple-choice questions, and view a leaderboard.

This folder contains the **frontend application**, built with React and Vite.

## Features

### Player Interface
- Enter an 8-digit Game PIN to join a quiz.
- Enter a nickname before joining.
- View a waiting lobby before the quiz begins.
- View questions and multiple-choice options.
- Select an answer on the question screen.
- Access a temporary question-screen navigation button for testing.

### Admin Interface
- Admin login page.
- Admin dashboard for accessing quiz management features.
- Create and manage quizzes.
- Prepare quizzes for presentation.
- Open a separate projector screen.
- Display a Game PIN and QR code for participants to join.

### Presentation Interface
- Display quiz questions on a projector screen.
- Provide host controls for starting the quiz and navigating between questions.
- Display the leaderboard interface.

## Technology Stack

- **React** — building reusable UI components.
- **Vite** — development server and production build tool.
- **JavaScript (JSX)** — frontend logic and components.
- **CSS** — styling and responsive layouts.
- **React Router** — page navigation, where configured.
- **qrcode.react** — generating QR codes, where used in the presentation interface.

## Project Structure

```text
frontend/
├── public/                  # Public assets
├── src/
│   ├── assets/              # Images and other assets
│   ├── components/          # Reusable UI components
│   │   └── game/            # Quiz-related components
│   ├── data/                # Mock quiz/question data
│   ├── pages/               # Application pages
│   ├── services/            # API and question services
│   ├── store/               # Game state management
│   ├── App.jsx              # Main application and routing
│   ├── App.css              # Application styles
│   └── index.css            # Global styles
├── index.html
├── package.json
├── package-lock.json
└── vite.config.js
```

## Prerequisites

Install the following before running the application:

- Node.js (LTS version recommended).
- npm, which is included with Node.js.
- Git, if you need to clone the repository.

Verify your installation:

```bash
node --version
npm --version
```

## Getting Started

### 1. Open the frontend directory

From the root of the QuizVoro repository:

```bash
cd frontend
```

### 2. Install dependencies

```bash
npm install
```

### 3. Start the development server

```bash
npm run dev
```

Open the local URL printed in the terminal, usually `http://localhost:5173`.

### 4. Build for production

```bash
npm run build
```

Vite generates the production build in the `dist/` directory.

To preview the production build locally:

```bash
npm run preview
```

## Current Implementation Status

The frontend currently includes player-facing screens, admin pages, quiz creation interfaces, presentation screens, and initial Game PIN and QR code functionality.

**Mock functionality:** Mock data and mock service logic are currently used for parts of quiz creation, quiz fetching, and answer submission.

**Pending work:** Actual backend integration, live synchronization between participants and the projector, real answer validation and scoring, and further UI polishing for the admin dashboard and leaderboard.

The exact behavior of each feature depends on the current implementation and its integration status.

## Backend Integration

The frontend will be connected to the QuizVoro backend APIs as they become available.

The backend repository documentation describes a FastAPI application with PostgreSQL for authentication and quiz management. Frontend API endpoints, request/response formats, authentication, and real-time communication must be aligned with the backend implementation.

## Development Workflow

Frontend development is carried out on a feature branch rather than directly on `master`.

Example branch:

```bash
git switch feature/frontend-ui
```

After making changes:

```bash
git add frontend
git commit -m "Update Asteris frontend"
git push
```

Pushes to the same branch update the existing Pull Request, provided it is still open.

## Notes

- Do not commit `node_modules/`, private `.env` files, passwords, or API secrets.
- Keep mock functionality clearly identified until it is replaced with actual backend integration.
- Test the application and production build before submitting changes for review.

---

**Project:** Asteris — Live Quiz Platform  
**Repository:** [QuizVoro on GitHub](https://github.com/Surya-nara0123/QuizVoro)  
**Area:** Frontend development
