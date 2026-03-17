import { formatPercent, request } from "../core/api.js";
import {
    applyResponse,
    attachQuestionConfig,
    formatCorrectAnswer,
    lockQuestionCard,
    renderQuestionCard,
    showFeedback,
} from "../components/questions.js";

export async function initResultsPage(pageContext) {
    const summary = document.getElementById("results-summary");
    const kpis = document.getElementById("results-kpis");
    const questionContainer = document.getElementById("results-questions");

    const data = await request(`/api/attempts/${pageContext.attempt_id}/result`);
    const attempt = data.attempt;

    summary.innerHTML = `
        <div>
            <p class="eyebrow">${attempt.exam_code}</p>
            <h2>${attempt.exam_title}</h2>
            <p class="muted">Submitted attempt review with official evaluative results.</p>
        </div>
        <a class="button button--secondary" href="/dashboard">Open dashboard</a>
    `;

    kpis.innerHTML = [
        createKpi("Score", formatPercent(attempt.score_percent)),
        createKpi("Correct", attempt.correct_count),
        createKpi("Incorrect", attempt.incorrect_count),
        createKpi("Omitted", attempt.omitted_count),
    ].join("");

    questionContainer.innerHTML = "";
    data.questions.forEach((entry) => {
        const card = renderQuestionCard(entry.question, {
            mode: "results",
            index: entry.question_order,
            response: entry.response,
        });
        attachQuestionConfig(card, entry.question);
        lockQuestionCard(card);
        applyResponse(card, entry.response);
        showFeedback(card, {
            success: entry.result.is_correct,
            title: entry.result.is_correct ? "Correct" : entry.result.omitted ? "Omitted" : "Incorrect",
            body: `${formatCorrectAnswer(entry.question, entry.result.correct_answer)} ${entry.question.explanation || ""}`.trim(),
        });
        questionContainer.appendChild(card);
    });
}

function createKpi(label, value) {
    return `<div class="kpi-card"><span class="muted">${label}</span><strong>${value}</strong></div>`;
}
