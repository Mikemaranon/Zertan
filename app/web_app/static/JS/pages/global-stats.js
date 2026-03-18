import { escapeHtml, formatDuration, formatPercent, request } from "../core/api.js";

export async function initGlobalStatsPage() {
    const kpiContainer = document.getElementById("global-stats-kpis");
    const usersContainer = document.getElementById("global-stats-users");
    const activityContainer = document.getElementById("global-stats-activity");
    const examContainer = document.getElementById("global-stats-exams");
    const typeContainer = document.getElementById("global-stats-types");
    const topicContainer = document.getElementById("global-stats-topics");
    const tagContainer = document.getElementById("global-stats-tags");

    const data = await request("/api/statistics/platform");
    const platform = data.platform || {};
    const summary = platform.summary || {};

    kpiContainer.innerHTML = [
        kpiCard("Active users", `${Number(summary.active_users || 0)} / ${Number(summary.total_users || 0)}`),
        kpiCard("Submitted attempts", Number(summary.submitted_attempts || 0)),
        kpiCard("Questions answered", Number(summary.total_questions_answered || 0)),
        kpiCard("Global success rate", formatPercent(summary.global_success_rate)),
        kpiCard("Average completion time", formatDuration(summary.average_completion_time)),
        kpiCard("Average questions per attempt", Number(summary.average_questions_per_attempt || 0).toFixed(1)),
    ].join("");

    renderUserComparison(usersContainer, platform.users || [], data.current_user_id);
    renderWeeklyActivity(activityContainer, platform.activity_by_week || []);
    renderExamPerformance(examContainer, platform.by_exam || []);
    renderQuestionTypes(typeContainer, platform.by_question_type || []);
    renderInsightList(topicContainer, platform.hardest_topics || [], {
        labelKey: "topic",
        countKey: "answers_count",
        countLabel: "Answers",
    });
    renderTagCards(tagContainer, platform.hardest_tags || []);
}

function renderUserComparison(container, users, currentUserId) {
    if (!users.length) {
        container.innerHTML = `<div class="empty-state">No submitted attempts are available for comparison yet.</div>`;
        return;
    }

    const maxAttempts = Math.max(...users.map((user) => Number(user.submitted_attempts || 0)), 1);
    container.innerHTML = users
        .map((user) => {
            const isCurrentUser = Number(user.user_id) === Number(currentUserId);
            return `
                <article class="global-user-card${isCurrentUser ? " global-user-card--current" : ""}">
                    <div class="global-user-card__header">
                        <div>
                            <h3>${escapeHtml(user.display_name || user.login_name || "User")}</h3>
                            <p class="muted">${escapeHtml(user.login_name || "")} · ${escapeHtml(user.role || "user")}</p>
                        </div>
                        <span class="badge">${escapeHtml(user.status || "")}</span>
                    </div>
                    <div class="global-user-card__metrics">
                        ${metricStrip("Success rate", user.success_rate, 100, formatPercent(user.success_rate))}
                        ${metricStrip("Attempt volume", user.submitted_attempts, maxAttempts, `${Number(user.submitted_attempts || 0)} attempts`)}
                    </div>
                    <div class="global-user-card__stats">
                        <span><strong>${Number(user.questions_answered || 0)}</strong> questions answered</span>
                        <span><strong>${Number(user.total_correct || 0)}</strong> correct</span>
                        <span><strong>${Number(user.total_incorrect || 0)}</strong> incorrect</span>
                        <span><strong>${Number(user.total_omitted || 0)}</strong> omitted</span>
                        <span><strong>${formatPercent(user.average_score)}</strong> average score</span>
                        <span><strong>${formatDuration(user.average_completion_time)}</strong> average duration</span>
                    </div>
                </article>
            `;
        })
        .join("");
}

function renderWeeklyActivity(container, weeks) {
    if (!weeks.length) {
        container.innerHTML = `<div class="empty-state">No weekly activity is available yet.</div>`;
        return;
    }
    const maxAttempts = Math.max(...weeks.map((week) => Number(week.attempts || 0)), 1);
    container.innerHTML = weeks
        .map((week) => {
            const attempts = Number(week.attempts || 0);
            const height = attempts <= 0 ? 12 : Math.max(24, Math.round((attempts / maxAttempts) * 160));
            return `
                <div class="global-week-bar">
                    <div class="global-week-bar__value" style="height: ${height}px"></div>
                    <strong>${attempts}</strong>
                    <span class="muted">${escapeHtml(formatWeekLabel(week.week_start))}</span>
                    <span class="muted">${Number(week.active_users || 0)} active users</span>
                </div>
            `;
        })
        .join("");
}

function renderExamPerformance(container, exams) {
    if (!exams.length) {
        container.innerHTML = `<div class="empty-state">No exam-level activity is available yet.</div>`;
        return;
    }
    const maxAttempts = Math.max(...exams.map((exam) => Number(exam.attempts || 0)), 1);
    container.innerHTML = exams
        .map((exam) => `
            <article class="global-insight-card">
                <div class="global-insight-card__header">
                    <div>
                        <h3>${escapeHtml(exam.code || "")}</h3>
                        <p class="muted">${escapeHtml(exam.title || "")}</p>
                    </div>
                    <span class="badge">${Number(exam.active_users || 0)} users</span>
                </div>
                ${metricStrip("Attempt share", exam.attempts, maxAttempts, `${Number(exam.attempts || 0)} attempts`)}
                <div class="global-insight-card__meta">
                    <span>Average score: <strong>${formatPercent(exam.success_rate)}</strong></span>
                    <span>Average duration: <strong>${formatDuration(exam.average_completion_time)}</strong></span>
                </div>
            </article>
        `)
        .join("");
}

function renderQuestionTypes(container, items) {
    if (!items.length) {
        container.innerHTML = `<div class="empty-state">No question-type statistics are available yet.</div>`;
        return;
    }
    container.innerHTML = items
        .map((item) => `
            <article class="global-insight-card">
                <div class="global-insight-card__header">
                    <div>
                        <h3>${escapeHtml(String(item.question_type || "").replaceAll("_", " "))}</h3>
                        <p class="muted">${Number(item.total_answers || 0)} evaluated answers</p>
                    </div>
                </div>
                ${metricStrip("Success rate", item.success_rate, 100, formatPercent(item.success_rate))}
            </article>
        `)
        .join("");
}

function renderInsightList(container, items, { labelKey, countKey, countLabel }) {
    if (!items.length) {
        container.innerHTML = `<div class="empty-state">No comparable data is available yet.</div>`;
        return;
    }
    container.innerHTML = items
        .map((item) => `
            <article class="global-insight-card">
                <div class="global-insight-card__header">
                    <div>
                        <h3>${escapeHtml(item[labelKey] || "")}</h3>
                        <p class="muted">${countLabel}: ${Number(item[countKey] || 0)}</p>
                    </div>
                </div>
                ${metricStrip("Success rate", item.success_rate, 100, formatPercent(item.success_rate))}
            </article>
        `)
        .join("");
}

function renderTagCards(container, tags) {
    if (!tags.length) {
        container.innerHTML = `<div class="empty-state">No tag-level comparisons are available yet.</div>`;
        return;
    }
    container.innerHTML = tags
        .map((tag) => `
            <div class="card global-tag-card">
                <h3>${escapeHtml(tag.tag || "")}</h3>
                <p class="muted">${Number(tag.answers_count || 0)} evaluated answers</p>
                ${metricStrip("Success rate", tag.success_rate, 100, formatPercent(tag.success_rate))}
            </div>
        `)
        .join("");
}

function metricStrip(label, value, maxValue, metaLabel) {
    const numericValue = Number(value || 0);
    const ratio = maximumSafeRatio(numericValue, maxValue);
    const width = numericValue <= 0 ? 0 : Math.max(8, Math.round(ratio * 100));
    return `
        <div class="metric-strip">
            <div class="metric-strip__topline">
                <span class="muted">${escapeHtml(label)}</span>
                <strong>${escapeHtml(metaLabel)}</strong>
            </div>
            <div class="metric-strip__track">
                <span class="metric-strip__fill" style="width: ${width}%"></span>
            </div>
        </div>
    `;
}

function maximumSafeRatio(value, maxValue) {
    const safeMax = Number(maxValue || 0);
    if (safeMax <= 0) {
        return 0;
    }
    return Math.max(0, Math.min(1, Number(value || 0) / safeMax));
}

function formatWeekLabel(value) {
    if (!value) {
        return "n/a";
    }
    const date = new Date(`${value}T00:00:00`);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return new Intl.DateTimeFormat(undefined, {
        month: "short",
        day: "numeric",
    }).format(date);
}

function kpiCard(label, value) {
    return `
        <div class="kpi-card">
            <span class="muted">${escapeHtml(label)}</span>
            <strong>${escapeHtml(value)}</strong>
        </div>
    `;
}
