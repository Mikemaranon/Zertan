import { getPageContext, isMobileViewport, request } from "./core/api.js";
import { bindProfileModal } from "./components/profile-modal.js";
import { initAccessInfoPage } from "./pages/access-info.js";
import { initAdminPage } from "./pages/admin.js";
import { initCatalogPage } from "./pages/catalog.js";
import { initDashboardPage } from "./pages/dashboard.js";
import { initExamBuilderPage } from "./pages/exam-builder.js";
import { initExamDetailPage } from "./pages/exam-detail.js";
import { initExamRunnerPage } from "./pages/exam-runner.js";
import { initGlobalStatsPage } from "./pages/global-stats.js";
import { initLiveExamsPage } from "./pages/live-exams.js";
import { initLoginPage } from "./pages/login.js";
import { initLogRegistryDetailPage, initLogRegistryPage } from "./pages/log-registry.js";
import { initManagementPage } from "./pages/management.js";
import { initQuestionManagementPage } from "./pages/question-management.js";
import { initQuestionEditorPage } from "./pages/question-editor.js";
import { initResultsPage } from "./pages/results.js";

const pageMap = {
    login: initLoginPage,
    "access-info": initAccessInfoPage,
    dashboard: initDashboardPage,
    "global-stats": initGlobalStatsPage,
    catalog: initCatalogPage,
    "live-exams": initLiveExamsPage,
    "log-registry": initLogRegistryPage,
    "log-registry-detail": initLogRegistryDetailPage,
    "exam-detail": initExamDetailPage,
    "exam-builder": initExamBuilderPage,
    "exam-runner": initExamRunnerPage,
    results: initResultsPage,
    "exam-management": initManagementPage,
    "question-management": initQuestionManagementPage,
    "question-editor": initQuestionEditorPage,
    admin: initAdminPage,
};

document.addEventListener("DOMContentLoaded", async () => {
    const page = document.body.dataset.page;
    const context = getPageContext();

    highlightActiveNavigation();
    bindSidebarToggle();
    bindLogoutButton();
    bindMobileKeyboardDismissal();
    bindProfileModal();

    const initializer = pageMap[page];
    if (!initializer) {
        return;
    }

    try {
        await initializer(context);
    } catch (error) {
        console.error(error);
        showGlobalError(error.message);
    }
});

function highlightActiveNavigation() {
    const links = document.querySelectorAll(".sidebar-nav a");
    const currentPath = window.location.pathname;
    links.forEach((link) => {
        if (link.getAttribute("href") === currentPath) {
            link.classList.add("active");
        }
    });
}

function bindLogoutButton() {
    const button = document.getElementById("logout-button");
    if (!button) {
        return;
    }
    button.addEventListener("click", async () => {
        try {
            await request("/api/auth/logout", { method: "POST" });
        } catch (error) {
            console.error(error);
        } finally {
            window.location.href = "/login";
        }
    });
}

function bindMobileKeyboardDismissal() {
    document.addEventListener("pointerdown", (event) => {
        if (!isMobileViewport()) {
            return;
        }

        const activeElement = document.activeElement;
        if (!isEditableElement(activeElement)) {
            return;
        }

        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }

        if (target.closest("input, textarea, select, [contenteditable='true'], label")) {
            return;
        }

        if (target.closest("[data-floating-panel='true']")) {
            return;
        }

        if (target.closest("button, a, [role='button'], .button")) {
            activeElement.blur();
        }
    });
}

function isEditableElement(element) {
    if (!(element instanceof HTMLElement)) {
        return false;
    }
    if (element.isContentEditable) {
        return true;
    }
    return ["INPUT", "TEXTAREA", "SELECT"].includes(element.tagName);
}

function bindSidebarToggle() {
    const toggle = document.getElementById("sidebar-toggle");
    const menu = document.getElementById("sidebar-menu");
    if (!toggle || !menu) {
        return;
    }

    const closeMenu = () => {
        document.body.classList.remove("sidebar-open");
        toggle.setAttribute("aria-expanded", "false");
    };

    toggle.addEventListener("click", (event) => {
        event.stopPropagation();
        const isOpen = document.body.classList.toggle("sidebar-open");
        toggle.setAttribute("aria-expanded", String(isOpen));
    });

    menu.addEventListener("click", (event) => {
        if (event.target.closest("a") || event.target.closest("button")) {
            closeMenu();
        }
        event.stopPropagation();
    });

    document.addEventListener("click", () => {
        if (window.innerWidth <= 1024) {
            closeMenu();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeMenu();
        }
    });

    window.addEventListener("resize", () => {
        if (window.innerWidth > 1024) {
            closeMenu();
        }
    });
}

function showGlobalError(message) {
    const container = document.querySelector(".content-body");
    if (!container) {
        return;
    }
    const node = document.createElement("div");
    node.className = "panel";
    node.innerHTML = `<div class="error-message">${message}</div>`;
    container.prepend(node);
}
