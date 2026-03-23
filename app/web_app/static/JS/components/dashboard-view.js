import { escapeHtml, formatDuration, formatPercent } from "../core/api.js";

export function renderDashboardView(
    { kpiContainer, attemptsContainer, typeContainer, examContainer },
    { overviewData, personalData }
) {
    const kpis = overviewData.kpis || {};
    kpiContainer.innerHTML = [
        createKpi("Exams completed", kpis.exams_completed),
        createKpi("Questions answered", kpis.questions_answered),
        createKpi("Total correct", kpis.total_correct),
        createKpi("Total incorrect", kpis.total_incorrect),
        createKpi("Total omitted", kpis.total_omitted),
        createKpi("Global success rate", formatPercent(kpis.global_success_rate)),
        createKpi("Average completion time", formatDuration(kpis.average_completion_time)),
    ].join("");

    attemptsContainer.innerHTML = (overviewData.recent_attempts || []).length
        ? overviewData.recent_attempts.map(renderAttemptCard).join("")
        : `<div class="empty-state">No formal attempts yet.</div>`;
    syncRecentAttemptsHeight(attemptsContainer);

    typeContainer.innerHTML = (personalData.by_question_type || []).length
        ? personalData.by_question_type.map(renderQuestionTypeCard).join("")
        : `<div class="empty-state">No question-type statistics available yet.</div>`;

    examContainer.innerHTML = (overviewData.by_exam || []).length
        ? overviewData.by_exam.map(renderExamCard).join("")
        : `<div class="empty-state">No exam statistics available yet.</div>`;
}

export function renderDashboardLoadingState({ kpiContainer, attemptsContainer, typeContainer, examContainer }) {
    const loadingMarkup = `<div class="empty-state">Loading dashboard...</div>`;
    kpiContainer.innerHTML = loadingMarkup;
    attemptsContainer.innerHTML = loadingMarkup;
    attemptsContainer.style.maxHeight = "";
    typeContainer.innerHTML = loadingMarkup;
    examContainer.innerHTML = loadingMarkup;
}

function renderAttemptCard(attempt) {
    const href = attempt.status === "submitted" ? `/attempts/${attempt.id}/results` : `/attempts/${attempt.id}/run`;
    const scoreValue =
        attempt.score_percent === null || attempt.score_percent === undefined
            ? "in progress"
            : formatPercent(attempt.score_percent);
    return `
        <a class="card dashboard-attempt-card" href="${href}">
            <span class="badge dashboard-attempt-card__badge">${escapeHtml(attempt.status || "")}</span>
            <h3>${escapeHtml(attempt.exam_code || "")}</h3>
            <p class="muted">${escapeHtml(attempt.exam_title || "")}</p>
            <p>Score: ${scoreValue}</p>
        </a>
    `;
}

function renderQuestionTypeCard(item) {
    return `
        <div class="card">
            <h3>${escapeHtml(String(item.question_type || "").replaceAll("_", " "))}</h3>
            <p>Total answers: ${Number(item.total || 0)}</p>
            <p>Success rate: ${formatPercent(item.success_rate)}</p>
        </div>
    `;
}

function renderExamCard(exam) {
    return `
        <div class="card">
            <h3>${escapeHtml(exam.code || "")}</h3>
            <p class="muted">${escapeHtml(exam.title || "")}</p>
            <p>Attempts: ${Number(exam.attempts || 0)}</p>
            <p>Average score: ${formatPercent(exam.success_rate)}</p>
        </div>
    `;
}

function syncRecentAttemptsHeight(container) {
    container.classList.add("dashboard-attempts-scroll");
    const cards = [...container.querySelectorAll(".card")];
    if (cards.length <= 4) {
        container.style.maxHeight = "";
        return;
    }
    const styles = window.getComputedStyle(container);
    const gap = Number.parseFloat(styles.rowGap || styles.gap || "0") || 0;
    const maxHeight =
        cards.slice(0, 4).reduce((total, card) => total + card.offsetHeight, 0) + gap * 3;
    container.style.maxHeight = `${Math.ceil(maxHeight)}px`;
}

function createKpi(label, value) {
    return `
        <div class="kpi-card">
            <span class="muted">${escapeHtml(label)}</span>
            <strong>${escapeHtml(value)}</strong>
        </div>
    `;
}
