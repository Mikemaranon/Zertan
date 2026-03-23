import { renderDashboardView } from "../components/dashboard-view.js";
import { request } from "../core/api.js";

export async function initDashboardPage() {
    const [overviewData, personalData] = await Promise.all([
        request("/api/statistics/overview"),
        request("/api/statistics/me"),
    ]);
    renderDashboardView(
        {
            kpiContainer: document.getElementById("dashboard-kpis"),
            attemptsContainer: document.getElementById("dashboard-attempts"),
            typeContainer: document.getElementById("dashboard-types"),
            examContainer: document.getElementById("dashboard-exams"),
        },
        { overviewData, personalData }
    );
}
