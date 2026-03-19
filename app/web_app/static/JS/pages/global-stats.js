import { escapeHtml, formatDuration, formatPercent, getCurrentUser, request } from "../core/api.js";

const USER_COMPARISON_KPIS = [
    {
        key: "submitted_attempts",
        label: "Number of attempts",
        shortLabel: "Attempts",
        color: "#66a8e0",
        scaleMode: "range",
        getValue: (user) => Number(user.submitted_attempts || 0),
        formatValue: (value) => `${Math.round(Number(value || 0))} attempts`,
    },
    {
        key: "success_rate",
        label: "% success",
        shortLabel: "Success",
        color: "#2a8b57",
        scaleMode: "percentage",
        getValue: (user) => Number(user.success_rate || 0),
        formatValue: (value) => formatPercent(value),
    },
    {
        key: "average_completion_time",
        label: "Average completion time",
        shortLabel: "Avg time",
        color: "#d48f3f",
        scaleMode: "range",
        betterDirection: "lower",
        getValue: (user) => Number(user.average_completion_time || 0),
        formatValue: (value) => formatDurationLabel(value),
    },
    {
        key: "questions_answered",
        label: "Questions answered",
        shortLabel: "Answered",
        color: "#7d6fd1",
        scaleMode: "range",
        getValue: (user) => Number(user.questions_answered || 0),
        formatValue: (value) => `${Math.round(Number(value || 0))} questions`,
    },
];

const DEFAULT_ACTIVE_USER_KPIS = ["submitted_attempts", "success_rate"];

export async function initGlobalStatsPage() {
    const kpiContainer = document.getElementById("global-stats-kpis");
    const usersContainer = document.getElementById("global-stats-users");
    const examContainer = document.getElementById("global-stats-exams");
    const typeContainer = document.getElementById("global-stats-types");
    const topicContainer = document.getElementById("global-stats-topics");
    const tagContainer = document.getElementById("global-stats-tags");

    const data = await request("/api/statistics/platform");
    const currentUser = getCurrentUser();
    const pageNodes = {
        kpiContainer,
        examContainer,
        typeContainer,
        topicContainer,
        tagContainer,
    };

    const userComparisonState = {
        activeMetricKeys: DEFAULT_ACTIVE_USER_KPIS.slice(),
        currentUserId: Number(data.current_user_id || 0),
        currentUserRole: String(data.current_user_role || currentUser.role || "user"),
        selectedGroupId: data.selected_group_id ? Number(data.selected_group_id) : null,
        availableGroups: data.comparison_groups || [],
        users: filterComparableUsers(data.platform?.users || []),
    };
    const comparisonControls = ensureUserComparisonControls(usersContainer);

    await bindUserComparisonEvents(
        comparisonControls.usersContainer,
        comparisonControls.kpiTogglesContainer,
        comparisonControls.groupSelect,
        comparisonControls.groupHint,
        userComparisonState,
        pageNodes,
    );
    populateGroupSelect(
        comparisonControls.groupSelect,
        comparisonControls.groupHint,
        userComparisonState.currentUserRole,
        userComparisonState.availableGroups,
        userComparisonState.selectedGroupId,
    );
    renderPlatformPanels(pageNodes, data.platform || {}, comparisonControls.usersContainer, comparisonControls.kpiTogglesContainer, userComparisonState);
}

function ensureUserComparisonControls(usersContainer) {
    const existingTogglesContainer = document.getElementById("global-stats-kpi-toggles");
    const existingGroupSelect = document.getElementById("global-stats-group-select");
    const existingGroupHint = document.getElementById("global-stats-group-hint");

    if (existingTogglesContainer && existingGroupSelect && existingGroupHint) {
        return {
            usersContainer,
            kpiTogglesContainer: existingTogglesContainer,
            groupSelect: existingGroupSelect,
            groupHint: existingGroupHint,
        };
    }

    const comparisonLayout = usersContainer?.closest(".global-comparison-layout");
    if (comparisonLayout) {
        comparisonLayout.innerHTML = `
            <div class="global-comparison-toolbar">
                <label class="global-comparison-field" for="global-stats-group-select">
                    <span>Group scope</span>
                    <select id="global-stats-group-select" aria-describedby="global-stats-group-hint"></select>
                </label>
                <div class="global-comparison-note">
                    <p id="global-stats-group-hint" class="muted">Global stats currently include every available user in the domain.</p>
                    <p class="muted">Only non-administrator users are represented in the comparison chart.</p>
                </div>
            </div>
            <div id="global-stats-users" class="global-user-chart-shell"></div>
            <div class="global-comparison-footer">
                <div>
                    <h3>KPI selection</h3>
                    <p class="muted">The first active KPI defines descending user order. Additional KPIs only add grouped columns.</p>
                </div>
                <div id="global-stats-kpi-toggles" class="global-kpi-toggles" aria-label="Toggle KPIs"></div>
            </div>
        `;
    }

    return {
        usersContainer: document.getElementById("global-stats-users"),
        kpiTogglesContainer: document.getElementById("global-stats-kpi-toggles"),
        groupSelect: document.getElementById("global-stats-group-select"),
        groupHint: document.getElementById("global-stats-group-hint"),
    };
}

async function bindUserComparisonEvents(chartContainer, togglesContainer, groupSelect, groupHint, state, pageNodes) {
    if (togglesContainer && !togglesContainer.dataset.bound) {
        togglesContainer.addEventListener("click", (event) => {
            const button = event.target.closest("[data-kpi-key]");
            if (!button) {
                return;
            }
            toggleActiveMetric(state, button.dataset.kpiKey);
            renderUserComparison(chartContainer, togglesContainer, state);
        });
        togglesContainer.dataset.bound = "true";
    }

    if (chartContainer && !chartContainer.dataset.bound) {
        chartContainer.addEventListener("click", (event) => {
            const bar = event.target.closest(".global-user-bar");
            if (!bar) {
                return;
            }
            const selected = chartContainer.querySelector(".global-user-bar.is-selected");
            if (selected && selected !== bar) {
                selected.classList.remove("is-selected");
            }
            bar.classList.toggle("is-selected");
        });
        chartContainer.dataset.bound = "true";
    }

    if (groupSelect && !groupSelect.dataset.bound) {
        groupSelect.addEventListener("change", async () => {
            const previousGroupId = state.selectedGroupId;
            groupSelect.disabled = true;
            const nextGroupId = parseSelectedGroupId(groupSelect.value);
            try {
                const data = await request(buildPlatformStatisticsUrl(nextGroupId));
                state.selectedGroupId = data.selected_group_id ? Number(data.selected_group_id) : null;
                state.availableGroups = data.comparison_groups || state.availableGroups;
                state.users = filterComparableUsers(data.platform?.users || []);
                populateGroupSelect(groupSelect, groupHint, state.currentUserRole, state.availableGroups, state.selectedGroupId);
                renderPlatformPanels(pageNodes, data.platform || {}, chartContainer, togglesContainer, state);
            } catch (error) {
                populateGroupSelect(groupSelect, groupHint, state.currentUserRole, state.availableGroups, previousGroupId);
                updateGroupHint(groupHint, state.currentUserRole, groupSelect, {
                    tone: "error",
                    customMessage: error.message,
                });
            } finally {
                groupSelect.disabled = false;
            }
        });
        groupSelect.dataset.bound = "true";
    }
}

function renderPlatformPanels(pageNodes, platform, usersContainer, togglesContainer, userComparisonState) {
    const summary = platform.summary || {};
    pageNodes.kpiContainer.innerHTML = [
        kpiCard("Active users", `${Number(summary.active_users || 0)} / ${Number(summary.total_users || 0)}`),
        kpiCard("Submitted attempts", Number(summary.submitted_attempts || 0)),
        kpiCard("Questions answered", Number(summary.total_questions_answered || 0)),
        kpiCard("Global success rate", formatPercent(summary.global_success_rate)),
        kpiCard("Average completion time", formatDuration(summary.average_completion_time)),
        kpiCard("Average questions per attempt", Number(summary.average_questions_per_attempt || 0).toFixed(1)),
    ].join("");
    renderUserComparison(usersContainer, togglesContainer, userComparisonState);
    renderExamPerformance(pageNodes.examContainer, platform.by_exam || []);
    renderQuestionTypes(pageNodes.typeContainer, platform.by_question_type || []);
    renderTopicCards(pageNodes.topicContainer, platform.hardest_topics || []);
    renderTagCards(pageNodes.tagContainer, platform.hardest_tags || []);
}

function populateGroupSelect(select, hintNode, currentUserRole, groups, selectedGroupId) {
    if (!select || !hintNode) {
        return;
    }
    const allLabel = currentUserRole === "administrator" ? "All domain users" : "All visible users";
    const options = [{ value: "", label: allLabel }, ...(groups || []).map((group) => ({
        value: String(group.id),
        label: group.name,
    }))];
    select.innerHTML = options
        .map(
            (option) => `
                <option value="${escapeHtml(option.value)}">${escapeHtml(option.label)}</option>
            `,
        )
        .join("");
    select.value = selectedGroupId ? String(selectedGroupId) : "";
    updateGroupHint(hintNode, currentUserRole, select);
}

function updateGroupHint(hintNode, currentUserRole, select, { tone = "default", customMessage = "" } = {}) {
    if (!hintNode || !select) {
        return;
    }
    if (customMessage) {
        hintNode.textContent = customMessage;
        hintNode.dataset.tone = tone;
        return;
    }
    const selectedLabel = select.options[select.selectedIndex]?.textContent || "Current selection";
    const scopeMessage = select.value
        ? `Global stats are filtered to "${selectedLabel}".`
        : currentUserRole === "administrator"
            ? "Global stats currently include every available user in the domain."
            : "Global stats currently include every available user visible on this workspace.";
    hintNode.textContent = scopeMessage;
    hintNode.dataset.tone = tone;
}

function renderUserComparison(container, togglesContainer, state) {
    renderKpiToggles(togglesContainer, state.activeMetricKeys);

    if (!state.users.length) {
        container.innerHTML = `<div class="empty-state">No non-administrator users are available for comparison yet.</div>`;
        return;
    }

    const activeMetrics = getActiveMetrics(state.activeMetricKeys);
    const orderingMetric = activeMetrics[0];
    const scales = buildMetricScales(state.users, activeMetrics);
    const orderedUsers = sortUsersByMetric(state.users, orderingMetric);
    container.innerHTML = `
        <div class="global-user-chart-card">
            <div class="global-user-chart-card__header">
                <div>
                    <h3>Grouped KPI comparison</h3>
                    <p class="muted">Users are ordered by ${escapeHtml(orderingMetric.label)}. Percentage KPIs keep their real percentage scale, while numeric KPIs are scaled proportionally against the highest visible value.</p>
                </div>
                <span class="badge">${orderedUsers.length} users</span>
            </div>
            <div class="global-user-chart-legend">
                ${activeMetrics.map((metric) => renderLegendItem(metric)).join("")}
            </div>
            <div class="global-user-chart-viewport">
                <div class="global-user-chart-stage" style="grid-template-columns: repeat(${orderedUsers.length}, var(--user-column-width));">
                    ${orderedUsers
                        .map((user) => renderUserColumn(user, activeMetrics, scales, orderingMetric, state.currentUserId))
                        .join("")}
                </div>
            </div>
        </div>
    `;
}

function renderKpiToggles(container, activeMetricKeys) {
    if (!container) {
        return;
    }
    container.innerHTML = USER_COMPARISON_KPIS.map((metric) => {
        const orderIndex = activeMetricKeys.indexOf(metric.key);
        const isActive = orderIndex >= 0;
        return `
            <button
                class="button button--secondary button--small global-kpi-toggle${isActive ? " is-active" : ""}"
                type="button"
                data-kpi-key="${escapeHtml(metric.key)}"
                data-active="${isActive ? "true" : "false"}"
                aria-pressed="${isActive ? "true" : "false"}"
                style="--toggle-accent: ${metric.color};"
            >
                <span class="global-kpi-toggle__swatch" aria-hidden="true"></span>
                <span>${escapeHtml(metric.label)}</span>
                <span class="global-kpi-toggle__order">${isActive ? orderIndex + 1 : "+"}</span>
            </button>
        `;
    }).join("");
}

function renderLegendItem(metric) {
    return `
        <span class="global-user-chart-legend__item">
            <span class="global-user-chart-legend__swatch" style="--legend-color: ${metric.color};" aria-hidden="true"></span>
            <span>${escapeHtml(metric.shortLabel)}</span>
        </span>
    `;
}

function renderUserColumn(user, activeMetrics, scales, orderingMetric, currentUserId) {
    const displayName = user.display_name || user.login_name || "User";
    const orderMetricValue = orderingMetric.formatValue(orderingMetric.getValue(user));
    const isCurrentUser = Number(user.user_id) === Number(currentUserId);

    return `
        <article class="global-user-column${isCurrentUser ? " global-user-column--current" : ""}">
            <div class="global-user-column__plot">
                <div class="global-user-column__bars">
                    ${activeMetrics.map((metric) => renderUserBar(user, metric, scales[metric.key])).join("")}
                </div>
            </div>
            <div class="global-user-column__meta">
                <strong title="${escapeHtml(displayName)}">${escapeHtml(displayName)}</strong>
                <span class="muted">${escapeHtml(orderMetricValue)}</span>
                ${isCurrentUser ? `<span class="global-user-column__you">You</span>` : ""}
            </div>
        </article>
    `;
}

function renderUserBar(user, metric, scale) {
    const displayName = user.display_name || user.login_name || "User";
    const value = metric.getValue(user);
    const normalizedValue = normalizeMetricValue(value, scale, metric);
    const valueLabel = metric.formatValue(value);
    const tooltip = `${displayName} · ${metric.label}: ${valueLabel}`;

    return `
        <button
            class="global-user-bar"
            type="button"
            title="${escapeHtml(tooltip)}"
            aria-label="${escapeHtml(tooltip)}"
            style="--bar-height: ${normalizedValue}%; --bar-color: ${metric.color};"
        >
            <span class="global-user-bar__value">${escapeHtml(valueLabel)}</span>
        </button>
    `;
}

function filterComparableUsers(users) {
    return users.filter((user) => String(user.role || "").toLowerCase() !== "administrator");
}

function getActiveMetrics(activeMetricKeys) {
    const metrics = activeMetricKeys
        .map((key) => USER_COMPARISON_KPIS.find((metric) => metric.key === key))
        .filter(Boolean);

    return metrics.length ? metrics : [USER_COMPARISON_KPIS[0]];
}

function toggleActiveMetric(state, metricKey) {
    const currentIndex = state.activeMetricKeys.indexOf(metricKey);
    if (currentIndex >= 0) {
        if (state.activeMetricKeys.length === 1) {
            return;
        }
        state.activeMetricKeys.splice(currentIndex, 1);
        return;
    }
    state.activeMetricKeys.push(metricKey);
}

function buildMetricScales(users, metrics) {
    return Object.fromEntries(
        metrics.map((metric) => {
            const values = users.map((user) => metric.getValue(user));
            return [
                metric.key,
                {
                    min: Math.min(...values),
                    max: Math.max(...values),
                },
            ];
        }),
    );
}

function normalizeMetricValue(value, scale, metric) {
    const numericValue = Number(value || 0);
    if (metric.scaleMode === "percentage") {
        return numericValue > 0 ? Math.max(1, Math.min(100, numericValue)) : 0;
    }

    const max = Number(scale?.max || 0);
    if (!max && !numericValue) {
        return 0;
    }
    return numericValue > 0 ? Math.max(6, Math.min(100, (numericValue / max) * 100)) : 0;
}

function parseSelectedGroupId(value) {
    if (!value) {
        return null;
    }
    const numericValue = Number(value);
    return Number.isFinite(numericValue) ? numericValue : null;
}

function buildPlatformStatisticsUrl(groupId) {
    const params = new URLSearchParams();
    if (groupId) {
        params.set("group_id", String(groupId));
    }
    const query = params.toString();
    return query ? `/api/statistics/platform?${query}` : "/api/statistics/platform";
}

function sortUsersByMetric(users, metric) {
    return users
        .slice()
        .sort((left, right) => {
            const valueDelta = metric.betterDirection === "lower"
                ? metric.getValue(left) - metric.getValue(right)
                : metric.getValue(right) - metric.getValue(left);
            if (valueDelta !== 0) {
                return valueDelta;
            }
            const leftName = (left.display_name || left.login_name || "").toLowerCase();
            const rightName = (right.display_name || right.login_name || "").toLowerCase();
            return leftName.localeCompare(rightName);
        });
}

function formatDurationLabel(seconds) {
    return Number(seconds || 0) > 0 ? formatDuration(seconds) : "0s";
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

function renderTopicCards(container, topics) {
    if (!topics.length) {
        container.innerHTML = `<div class="empty-state">No comparable data is available yet.</div>`;
        return;
    }
    container.innerHTML = topics
        .map((topic) => `
            <div class="card global-tag-card">
                <h3>${escapeHtml(topic.topic || "")}</h3>
                <p class="muted">${Number(topic.answers_count || 0)} evaluated answers</p>
                ${metricStrip("Success rate", topic.success_rate, 100, formatPercent(topic.success_rate))}
            </div>
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
