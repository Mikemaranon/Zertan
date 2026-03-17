import { formatDuration, formatPercent, request } from "../core/api.js";

export async function initProfilePage() {
    const kpiContainer = document.getElementById("profile-kpis");
    const examContainer = document.getElementById("profile-by-exam");
    const typeContainer = document.getElementById("profile-by-type");

    const data = await request("/api/statistics/me");
    const kpis = data.kpis;
    kpiContainer.innerHTML = [
        card("Exams completed", kpis.exams_completed),
        card("Questions answered", kpis.questions_answered),
        card("Success rate", formatPercent(kpis.global_success_rate)),
        card("Average completion time", formatDuration(kpis.average_completion_time)),
    ].join("");

    examContainer.innerHTML = data.by_exam.length
        ? data.by_exam
              .map(
                  (exam) => `
            <div class="card">
                <h3>${exam.code}</h3>
                <p class="muted">${exam.title}</p>
                <p>Attempts: ${exam.attempts}</p>
                <p>Success rate: ${formatPercent(exam.success_rate)}</p>
            </div>
        `
              )
              .join("")
        : `<div class="empty-state">No submitted attempts yet.</div>`;

    typeContainer.innerHTML = data.by_question_type.length
        ? data.by_question_type
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
}

function card(label, value) {
    return `<div class="kpi-card"><span class="muted">${label}</span><strong>${value}</strong></div>`;
}
