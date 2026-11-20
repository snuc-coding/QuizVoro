
import { useEffect, useState } from "react";
import "./AnswerResultsChart.css";

export default function AnswerResultsChart({
  options = [],
  totalAnswers,
}) {
  const [animated, setAnimated] = useState(false);

  const calculatedTotal = options.reduce(
    (sum, option) => sum + (Number(option.votes) || 0),
    0
  );

  const answerTotal = totalAnswers ?? calculatedTotal;

  useEffect(() => {
    const timer = window.setTimeout(() => setAnimated(true), 80);
    return () => window.clearTimeout(timer);
  }, []);

  if (!options.length) {
    return <p className="results-empty">No answer options available.</p>;
  }

  const colors = ["#E6A700", "#00C9E8", "#84D600", "#FF4778"];

  return (
    <section className="answer-results" aria-label="Answer distribution">
      <h3 className="results-chart-title">ANSWER DISTRIBUTION</h3>
      <p className="results-subtitle">See how participants voted</p>

      <div className="results-chart">
        <div className="results-guides" aria-hidden="true">
          {[100, 75, 50, 25, 0].map((line) => (
            <div className="results-guide-line" key={line} />
          ))}
        </div>

        {options.map((option, index) => {
          const votes = Math.max(0, Number(option.votes) || 0);
          const percentage =
            answerTotal > 0
              ? Math.round((votes / answerTotal) * 100)
              : 0;

          const isCorrect = option.isCorrect === true;

          return (
            <div
              className="results-bar-column"
              key={option.id ?? option.label ?? index}
            >
              <span
                className={`results-percentage ${animated ? "visible" : ""}`}
                style={{ transitionDelay: `${index * 100}ms` }}
              >
                {percentage}%
              </span>

              <div className="results-bar-track">
                <div
                  className="results-bar"
                  style={{
                    height: animated ? `${percentage}%` : "0%",
                    backgroundColor: colors[index % colors.length],
                    transitionDelay: `${index * 100}ms`,
                  }}
                />
              </div>

              <span className="results-option-label">{option.label}</span>
              <span className="results-option-text">{option.text}</span>

              <div className="results-tick-slot">
                {isCorrect && (
                  <span
                    className="results-correct-tick"
                    aria-label="Correct answer"
                    title="Correct answer"
                  >
                    ✓
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <p className="results-total">
        {answerTotal} {answerTotal === 1 ? "answer" : "answers"} submitted
      </p>
    </section>
  );
}
