import { formatDuration, formatPercent, request } from "../core/api.js";

export async function initDashboardPage() {
    const kpiContainer = document.getElementById("dashboard-kpis");
    const attemptsContainer = document.getElementById("dashboard-attempts");
    const typeContainer = document.getElementById("dashboard-types");
    const examContainer = document.getElementById("dashboard-exams");

    const [overviewData, personalData] = await Promise.all([
        request("/api/statistics/overview"),
        request("/api/statistics/me"),
    ]);
    const kpis = overviewData.kpis;
    kpiContainer.innerHTML = [
        createKpi("Exams completed", kpis.exams_completed),
        createKpi("Questions answered", kpis.questions_answered),
        createKpi("Total correct", kpis.total_correct),
        createKpi("Total incorrect", kpis.total_incorrect),
        createKpi("Total omitted", kpis.total_omitted),
        createKpi("Global success rate", formatPercent(kpis.global_success_rate)),
        createKpi("Average completion time", formatDuration(kpis.average_completion_time)),
    ].join("");

    attemptsContainer.innerHTML = overviewData.recent_attempts.length
        ? overviewData.recent_attempts
              .map(
                  (attempt) => `
            <a class="card dashboard-attempt-card" href="${attempt.status === "submitted" ? `/attempts/${attempt.id}/results` : `/attempts/${attempt.id}/run`}">
                <span class="badge dashboard-attempt-card__badge">${attempt.status}</span>
                <h3>${attempt.exam_code}</h3>
                <p class="muted">${attempt.exam_title}</p>
                <p>Score: ${attempt.score_percent ? formatPercent(attempt.score_percent) : "in progress"}</p>
            </a>
        `
              )
              .join("")
        : `<div class="empty-state">No formal attempts yet.</div>`;
    syncRecentAttemptsHeight(attemptsContainer);

    typeContainer.innerHTML = personalData.by_question_type.length
        ? personalData.by_question_type
              .map(
                  (item) => `
            <div class="card">
                <h3>${item.question_type.replaceAll("_", " ")}</h3>
                <p>Total answers: ${item.total}</p>
                <p>Success rate: ${formatPercent(item.success_rate)}</p>
            </div>
        `
              )
              .join("")
        : `<div class="empty-state">No question-type statistics available yet.</div>`;

    examContainer.innerHTML = overviewData.by_exam.length
        ? overviewData.by_exam
              .map(
                  (exam) => `
            <div class="card">
                <h3>${exam.code}</h3>
                <p class="muted">${exam.title}</p>
                <p>Attempts: ${exam.attempts}</p>
                <p>Average score: ${formatPercent(exam.success_rate)}</p>
            </div>
        `
              )
              .join("")
        : `<div class="empty-state">No exam statistics available yet.</div>`;
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
            <span class="muted">${label}</span>
            <strong>${value}</strong>
        </div>
    `;
}
