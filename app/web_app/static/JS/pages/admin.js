import { renderDashboardLoadingState, renderDashboardView } from "../components/dashboard-view.js";
import { assetPathToUrl, escapeHtml, request } from "../core/api.js";

export async function initAdminPage() {
    const list = document.getElementById("admin-users-list");
    const scrollContainer = document.getElementById("admin-users-scroll");
    const searchInput = document.getElementById("admin-user-search");
    const form = document.getElementById("admin-user-form");
    const errorNode = document.getElementById("admin-error");
    const featureContainer = document.getElementById("admin-feature-toggles");
    const featureErrorNode = document.getElementById("admin-feature-error");
    const dashboardModal = bindAdminDashboardModal();
    let users = [];
    let features = [];

    function renderUsers() {
        const query = searchInput.value.trim().toLowerCase();
        const filteredUsers = users.filter((user) => {
            if (!query) {
                return true;
            }
            return [user.display_name, user.login_name, user.role, user.status].some((value) =>
                String(value).toLowerCase().includes(query)
            );
        });

        list.innerHTML = filteredUsers.length
            ? filteredUsers
            .map(
                (user) => `
            <div class="card" data-user-id="${user.id}">
                <div class="section-heading">
                    <div>
                        <h3>${escapeHtml(user.display_name)}</h3>
                        <p class="muted">${escapeHtml(user.login_name)}</p>
                    </div>
                    <span class="badge">${escapeHtml(user.role)}</span>
                </div>
                <p class="muted">Status: ${escapeHtml(user.status)}</p>
                <div class="button-row">
                    <button class="button button--secondary button--small js-view-user" type="button">View</button>
                    <button class="button button--secondary button--small js-edit-user" type="button">Edit</button>
                    <button class="button button--secondary button--small js-delete-user" type="button">Delete</button>
                </div>
            </div>
        `
            )
            .join("")
            : `<div class="empty-state">No users match the current search.</div>`;

        list.querySelectorAll(".js-edit-user").forEach((button) => {
            button.addEventListener("click", (event) => {
                const card = event.currentTarget.closest("[data-user-id]");
                const user = users.find((item) => String(item.id) === card.dataset.userId);
                fillUserForm(user);
            });
        });

        list.querySelectorAll(".js-view-user").forEach((button) => {
            button.addEventListener("click", (event) => {
                const card = event.currentTarget.closest("[data-user-id]");
                const user = users.find((item) => String(item.id) === card.dataset.userId);
                dashboardModal.open(user);
            });
        });

        list.querySelectorAll(".js-delete-user").forEach((button) => {
            button.addEventListener("click", async (event) => {
                const card = event.currentTarget.closest("[data-user-id]");
                await request(`/api/admin/users/${card.dataset.userId}`, { method: "DELETE" });
                await loadUsers();
            });
        });

        updateDirectoryHeight();
    }

    function updateDirectoryHeight() {
        const cards = [...list.querySelectorAll(".card")];
        if (!cards.length) {
            scrollContainer.style.maxHeight = "";
            return;
        }
        const grid = scrollContainer.closest(".grid--two");
        const gridTemplateColumns = grid ? window.getComputedStyle(grid).gridTemplateColumns : "";
        const isVerticalLayout = !gridTemplateColumns || !gridTemplateColumns.includes(" ");
        const styles = window.getComputedStyle(list);
        const gap = Number.parseFloat(styles.rowGap || styles.gap || "0") || 0;
        const panel = scrollContainer.closest(".panel");
        const panelStyles = panel ? window.getComputedStyle(panel) : null;
        const panelBottomPadding = Number.parseFloat(panelStyles?.paddingBottom || "0") || 0;
        const maxVisibleCards = isVerticalLayout ? 3 : 4;
        const totalHeight =
            cards.reduce((total, card) => total + card.offsetHeight, 0) + gap * Math.max(cards.length - 1, 0);
        const targetCardHeight =
            cards.slice(0, maxVisibleCards).reduce((total, card) => total + card.offsetHeight, 0) +
            gap * Math.max(Math.min(cards.length, maxVisibleCards) - 1, 0);
        const viewportSafetyOffset = 27;
        const availableViewportHeight = Math.max(
            220,
            window.innerHeight - scrollContainer.getBoundingClientRect().top - panelBottomPadding - viewportSafetyOffset
        );
        const desiredHeight = isVerticalLayout
            ? (cards.length > maxVisibleCards ? targetCardHeight : totalHeight)
            : (cards.length > maxVisibleCards ? Math.min(targetCardHeight, availableViewportHeight) : Math.min(totalHeight, availableViewportHeight));
        const constrainedHeight = totalHeight > desiredHeight ? Math.ceil(desiredHeight) : null;
        scrollContainer.style.maxHeight = constrainedHeight ? `${constrainedHeight}px` : "";
    }

    async function loadUsers() {
        const data = await request("/api/admin/users");
        users = data.users;
        renderUsers();
    }

    function renderFeatureToggles() {
        featureContainer.innerHTML = features.length
            ? features
                .map(
                    (feature) => `
                <label class="feature-toggle-row" data-feature-key="${feature.feature_key}">
                    <div class="feature-toggle-row__copy">
                        <strong>${escapeHtml(feature.label)}</strong>
                        <p class="muted">${escapeHtml(feature.description || "")}</p>
                    </div>
                    <span class="feature-toggle">
                        <input class="js-feature-toggle" type="checkbox" ${feature.enabled ? "checked" : ""}>
                        <span class="feature-toggle__track" aria-hidden="true"></span>
                    </span>
                </label>
            `
                )
                .join("")
            : `<div class="empty-state">No feature toggles are configured yet.</div>`;

        featureContainer.querySelectorAll(".js-feature-toggle").forEach((input) => {
            input.addEventListener("change", async (event) => {
                const row = event.currentTarget.closest("[data-feature-key]");
                const featureKey = row?.dataset.featureKey;
                const enabled = event.currentTarget.checked;
                const previousValue = !enabled;
                featureErrorNode.textContent = "";
                event.currentTarget.disabled = true;

                try {
                    const payload = await request(`/api/admin/features/${featureKey}`, {
                        method: "PUT",
                        body: { enabled },
                    });
                    features = features.map((feature) =>
                        feature.feature_key === featureKey ? payload.feature : feature
                    );
                    syncFeatureNavigation(payload.feature);
                    renderFeatureToggles();
                } catch (error) {
                    event.currentTarget.checked = previousValue;
                    event.currentTarget.disabled = false;
                    featureErrorNode.textContent = error.message;
                }
            });
        });
    }

    async function loadFeatures() {
        const data = await request("/api/admin/features");
        features = data.features;
        features.forEach(syncFeatureNavigation);
        renderFeatureToggles();
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        errorNode.textContent = "";
        const userId = document.getElementById("admin-user-id").value;
        const payload = {
            display_name: document.getElementById("admin-display-name").value.trim(),
            login_name: document.getElementById("admin-login-name").value.trim(),
            password: document.getElementById("admin-password").value,
            role: document.getElementById("admin-role").value,
            status: document.getElementById("admin-status").value,
        };
        try {
            await request(userId ? `/api/admin/users/${userId}` : "/api/admin/users", {
                method: userId ? "PUT" : "POST",
                body: payload,
            });
            resetForm();
            await loadUsers();
        } catch (error) {
            errorNode.textContent = error.message;
        }
    });

    document.getElementById("admin-form-reset").addEventListener("click", resetForm);
    searchInput.addEventListener("input", renderUsers);
    window.addEventListener("resize", updateDirectoryHeight);
    await Promise.all([loadUsers(), loadFeatures()]);
}

function fillUserForm(user) {
    const form = document.getElementById("admin-user-form");
    const nameInput = document.getElementById("admin-display-name");
    document.getElementById("admin-user-id").value = user.id;
    nameInput.value = user.display_name;
    document.getElementById("admin-login-name").value = user.login_name;
    document.getElementById("admin-password").value = "";
    document.getElementById("admin-role").value = user.role;
    document.getElementById("admin-status").value = user.status;
    const mobileHeaderHeight = Number.parseFloat(
        getComputedStyle(document.documentElement).getPropertyValue("--mobile-header-height") || "0"
    ) || 0;
    const viewportPadding = window.innerWidth <= 720 ? 16 : 24;
    const topOffset = window.innerWidth <= 1024 ? mobileHeaderHeight + viewportPadding + 23 : 55;
    const targetTop = Math.max(0, window.scrollY + form.getBoundingClientRect().top - topOffset);
    window.scrollTo({ top: targetTop, behavior: "smooth" });
    window.setTimeout(() => {
        nameInput.focus({ preventScroll: true });
        nameInput.select();
    }, 220);
}

function resetForm() {
    document.getElementById("admin-user-id").value = "";
    document.getElementById("admin-user-form").reset();
    document.getElementById("admin-role").value = "user";
    document.getElementById("admin-status").value = "active";
}

function syncFeatureNavigation(feature) {
    if (!feature) {
        return;
    }
    const featureLinks = {
        global_stats_page: {
            href: "/global-stats",
            label: "Global Stats",
            insertAfter: 'a[href="/dashboard"]',
        },
        live_exams_page: {
            href: "/live-exams",
            label: "Live Exams",
            insertAfter: 'a[href="/catalog"]',
        },
    };
    const config = featureLinks[feature.feature_key];
    if (!config) {
        return;
    }
    const nav = document.querySelector(".sidebar-nav");
    if (!nav) {
        return;
    }
    const existingLink = nav.querySelector(`a[href="${config.href}"]`);
    if (!feature.enabled) {
        existingLink?.remove();
        return;
    }
    if (existingLink) {
        return;
    }
    const anchor = nav.querySelector(config.insertAfter);
    const link = document.createElement("a");
    link.href = config.href;
    link.textContent = config.label;
    if (window.location.pathname === config.href) {
        link.classList.add("active");
    }
    if (anchor) {
        anchor.insertAdjacentElement("afterend", link);
        return;
    }
    nav.prepend(link);
}

function bindAdminDashboardModal() {
    const modal = document.getElementById("admin-dashboard-modal");
    if (!modal) {
        return { open() {} };
    }

    const closeButton = document.getElementById("admin-dashboard-modal-close");
    const backdrop = document.getElementById("admin-dashboard-modal-backdrop");
    const avatarNode = document.getElementById("admin-dashboard-avatar");
    const titleNode = document.getElementById("admin-dashboard-user-name");
    const subtitleNode = document.getElementById("admin-dashboard-subtitle");
    const loginNameNode = document.getElementById("admin-dashboard-login-name");
    const roleNode = document.getElementById("admin-dashboard-role");
    const statusNode = document.getElementById("admin-dashboard-status");
    const lastLoginNode = document.getElementById("admin-dashboard-last-login");
    const errorNode = document.getElementById("admin-dashboard-error");
    const dashboardNodes = {
        kpiContainer: document.getElementById("admin-dashboard-kpis"),
        attemptsContainer: document.getElementById("admin-dashboard-attempts"),
        typeContainer: document.getElementById("admin-dashboard-types"),
        examContainer: document.getElementById("admin-dashboard-exams"),
    };

    let isClosing = false;
    let requestSequence = 0;

    function open(user) {
        if (!user) {
            return;
        }
        requestSequence += 1;
        renderUserSummary(user);
        errorNode.textContent = "";
        renderDashboardLoadingState(dashboardNodes);
        showModal();
        void loadDashboard(user.id, requestSequence);
    }

    function showModal() {
        if (!modal.hidden && modal.dataset.state === "open") {
            return;
        }
        isClosing = false;
        modal.hidden = false;
        modal.dataset.state = "closed";
        document.body.classList.add("modal-open");
        window.requestAnimationFrame(() => {
            window.requestAnimationFrame(() => {
                modal.dataset.state = "open";
            });
        });
    }

    function closeModal() {
        if (modal.hidden || isClosing) {
            return;
        }
        isClosing = true;
        modal.dataset.state = "closing";
        document.body.classList.remove("modal-open");

        window.setTimeout(() => {
            modal.hidden = true;
            modal.dataset.state = "closed";
            isClosing = false;
        }, 300);
    }

    function renderUserSummary(user) {
        const displayName = user.display_name || user.login_name || "User";
        titleNode.textContent = displayName;
        subtitleNode.textContent = `Viewing the personal dashboard for ${displayName}.`;
        loginNameNode.textContent = user.login_name || "n/a";
        roleNode.textContent = user.role || "n/a";
        statusNode.textContent = user.status || "n/a";
        lastLoginNode.textContent = formatDateTime(user.last_login_at);

        avatarNode.textContent = "";
        avatarNode.innerHTML = "";
        if (user.avatar_path) {
            const image = document.createElement("img");
            image.className = "profile-avatar__image";
            image.src = assetPathToUrl(user.avatar_path);
            image.alt = `${displayName} profile photo`;
            avatarNode.appendChild(image);
            return;
        }
        avatarNode.textContent = initialsFor(displayName);
    }

    async function loadDashboard(userId, token) {
        try {
            const payload = await request(`/api/statistics/users/${userId}`);
            if (token !== requestSequence) {
                return;
            }
            renderUserSummary(payload.user);
            renderDashboardView(dashboardNodes, {
                overviewData: payload.overview,
                personalData: payload.personal,
            });
        } catch (error) {
            if (token !== requestSequence) {
                return;
            }
            errorNode.textContent = error.message;
            const failureMarkup = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
            dashboardNodes.kpiContainer.innerHTML = failureMarkup;
            dashboardNodes.attemptsContainer.innerHTML = failureMarkup;
            dashboardNodes.attemptsContainer.style.maxHeight = "";
            dashboardNodes.typeContainer.innerHTML = failureMarkup;
            dashboardNodes.examContainer.innerHTML = failureMarkup;
        }
    }

    closeButton.addEventListener("click", closeModal);
    backdrop.addEventListener("click", closeModal);

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !modal.hidden) {
            closeModal();
        }
    });

    return { open };
}

function initialsFor(value) {
    const tokens = String(value || "")
        .trim()
        .split(/\s+/)
        .filter(Boolean);
    if (!tokens.length) {
        return "?";
    }
    if (tokens.length === 1) {
        return tokens[0].slice(0, 1).toUpperCase();
    }
    return `${tokens[0][0]}${tokens[tokens.length - 1][0]}`.toUpperCase();
}

function formatDateTime(value) {
    if (!value) {
        return "Never";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
    }).format(date);
}
