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
            <a class="card" href="${attempt.status === "submitted" ? `/attempts/${attempt.id}/results` : `/attempts/${attempt.id}/run`}">
                <div class="section-heading">
                    <div>
                        <h3>${attempt.exam_code}</h3>
                        <p class="muted">${attempt.exam_title}</p>
                    </div>
                    <span class="badge">${attempt.status}</span>
                </div>
                <p class="muted">Score: ${attempt.score_percent ? formatPercent(attempt.score_percent) : "in progress"}</p>
            </a>
        `
              )
              .join("")
        : `<div class="empty-state">No formal attempts yet.</div>`;

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

function createKpi(label, value) {
    return `
        <div class="kpi-card">
            <span class="muted">${label}</span>
            <strong>${value}</strong>
        </div>
    `;
}
