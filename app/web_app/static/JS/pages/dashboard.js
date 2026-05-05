import {
    renderDashboardErrorState,
    renderDashboardLoadingState,
    renderDashboardView,
} from "../components/dashboard-view.js";
import { request } from "../core/api.js";

export async function initDashboardPage() {
    const nodes = {
        kpiContainer: document.getElementById("dashboard-kpis"),
        attemptsContainer: document.getElementById("dashboard-attempts"),
        typeContainer: document.getElementById("dashboard-types"),
        examContainer: document.getElementById("dashboard-exams"),
    };

    const loadDashboard = async () => {
        renderDashboardLoadingState(nodes);
        try {
            const [overviewData, personalData] = await Promise.all([
                request("/api/statistics/overview"),
                request("/api/statistics/me"),
            ]);
            renderDashboardView(nodes, { overviewData, personalData });
        } catch (error) {
            renderDashboardErrorState(nodes, error, loadDashboard);
        }
    };

    await loadDashboard();
}
