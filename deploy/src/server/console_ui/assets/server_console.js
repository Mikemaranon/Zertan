const NAV_SECTIONS = [
            {
                id: "overview",
                label: "Overview",
                helper: "Instance health, addresses, storage paths, and shortcuts."
            },
            {
                id: "directory",
                label: "Directory",
                helper: "Search users and groups with floating results over the content."
            },
            {
                id: "features",
                label: "Features",
                helper: "Quickly enable or disable site capabilities for the running domain."
            },
            {
                id: "activity",
                label: "API Log",
                helper: "Important API requests made against this server during the current runtime."
            }
        ];

        const state = {
            section: "overview",
            snapshot: window.__SERVER_CONSOLE_BOOTSTRAP__ || null,
            directoryQuery: "",
            directoryPanelOpen: false,
            activityFilter: "all",
            modalItem: null,
            featureBusy: {},
            stopping: false,
            navOpen: false
        };

        let refreshTimer = null;
        let initialized = false;

        function api() {
            return window.pywebview && window.pywebview.api ? window.pywebview.api : null;
        }

        function snapshot() {
            return state.snapshot || {
                server: {},
                stats: {},
                users: [],
                groups: [],
                features: [],
                activity: []
            };
        }

        function escapeHtml(value) {
            return String(value == null ? "" : value)
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#39;");
        }

        function createNode(tag, className, text) {
            const node = document.createElement(tag);
            if (className) {
                node.className = className;
            }
            if (text !== undefined) {
                node.textContent = text;
            }
            return node;
        }

        function badgeNode(className, text) {
            return createNode("span", className, text);
        }

        function buildBadgeForStatus(status) {
            const value = String(status || "").toLowerCase();
            if (value === "verified" || value === "healthy" || value === "active" || value === "enabled" || value === "success") {
                return "badge badge--ok";
            }
            if (value === "mismatch" || value === "warning" || value === "redirect") {
                return "badge badge--warning";
            }
            if (
                value === "disabled" ||
                value === "inactive" ||
                value === "error" ||
                value === "unreachable" ||
                value === "client_error" ||
                value === "server_error"
            ) {
                return "badge badge--danger";
            }
            return "badge badge--primary";
        }

        function directoryEntities() {
            const data = snapshot();
            const groupEntities = (data.groups || []).map((group) => ({
                id: `group-${group.id}`,
                kind: "group",
                title: group.name,
                helper: `${group.code} · ${group.member_count} members`,
                searchTerms: [
                    group.name,
                    group.code,
                    group.description || "",
                    ...(group.members || []).map((member) => member.display_name || member.login_name || "")
                ],
                payload: group
            }));
            const userEntities = (data.users || []).map((user) => ({
                id: `user-${user.id}`,
                kind: "user",
                title: user.display_name || user.login_name,
                helper: `${user.login_name} · ${user.role} · ${user.status}`,
                searchTerms: [
                    user.display_name,
                    user.login_name,
                    user.role,
                    user.status,
                    ...(user.group_names || [])
                ],
                payload: user
            }));
            return [...userEntities, ...groupEntities];
        }

        function filterDirectoryEntities() {
            const query = state.directoryQuery.trim().toLowerCase();
            const entities = directoryEntities();
            if (!query) {
                return entities.slice(0, 8);
            }
            return entities.filter((entity) => {
                const haystack = [
                    entity.kind,
                    entity.title,
                    entity.helper,
                    ...(entity.searchTerms || [])
                ].join(" ").toLowerCase();
                return haystack.includes(query);
            }).slice(0, 10);
        }

        function filterActivityItems() {
            const items = snapshot().activity || [];
            if (state.activityFilter === "all") {
                return items;
            }
            if (state.activityFilter === "write") {
                return items.filter((item) => String(item.method || "").toUpperCase() !== "GET");
            }
            if (state.activityFilter === "errors") {
                return items.filter((item) => Number(item.status_code || 0) >= 400);
            }
            return items;
        }

        function renderSidebar() {
            const data = snapshot();
            const server = data.server || {};
            const stats = data.stats || {};

            const badges = document.getElementById("sidebar-badges");
            badges.innerHTML = "";
            badges.append(
                badgeNode(buildBadgeForStatus(server.health_label), server.health_label || "Unknown"),
                badgeNode("badge badge--primary", `Port ${server.port || "-"}`),
                badgeNode("badge badge--warning", `${server.uptime_label || "00h 00m"}`),
                badgeNode("badge badge--primary", `${stats.active_sessions || 0} sessions`)
            );
        }

        function syncResponsiveHeaderMetrics() {
            const root = document.documentElement;
            const header = document.querySelector(".console-mobile-header");
            if (!header || window.innerWidth > 1100) {
                root.style.removeProperty("--server-console-mobile-header-offset");
                root.style.removeProperty("--server-console-mobile-content-offset");
                return;
            }
            const rect = header.getBoundingClientRect();
            const menuTop = Math.ceil(rect.bottom);
            const contentTop = Math.ceil(rect.bottom + 16);
            root.style.setProperty("--server-console-mobile-header-offset", `${menuTop}px`);
            root.style.setProperty("--server-console-mobile-content-offset", `${contentTop}px`);
        }

        function renderNav() {
            const desktopNode = document.getElementById("nav-list-desktop");
            const mobileNode = document.getElementById("nav-list-mobile");
            [desktopNode, mobileNode].forEach((node) => {
                if (!node) {
                    return;
                }
                node.innerHTML = "";
                NAV_SECTIONS.forEach((section) => {
                    const button = createNode("button", `nav-button${state.section === section.id ? " is-active" : ""}`);
                    button.type = "button";
                    button.append(
                        createNode("span", "nav-button__title", section.label),
                        createNode("span", "nav-button__helper", section.helper)
                    );
                    button.addEventListener("click", () => {
                        state.section = section.id;
                        if (section.id !== "directory") {
                            closeDirectoryPanel();
                        }
                        closeNavMenu();
                        renderAll();
                    });
                    node.append(button);
                });
            });
        }

        function syncNavMenuState() {
            const menu = document.getElementById("nav-menu");
            const toggle = document.getElementById("nav-toggle");
            const isMobile = window.innerWidth <= 1100;
            const shouldOpen = !!state.navOpen && isMobile;
            if (menu) {
                if (shouldOpen) {
                    menu.hidden = false;
                    menu.classList.add("is-open");
                } else {
                    menu.classList.remove("is-open");
                    menu.hidden = true;
                }
            }
            if (toggle) {
                toggle.setAttribute("aria-expanded", String(shouldOpen));
            }
            document.body.classList.toggle("server-console-nav-open", shouldOpen);
            requestAnimationFrame(syncResponsiveHeaderMetrics);
        }

        function closeNavMenu() {
            if (!state.navOpen) {
                syncNavMenuState();
                return;
            }
            state.navOpen = false;
            syncNavMenuState();
        }

        function buildOverviewView() {
            const data = snapshot();
            const server = data.server || {};
            const stats = data.stats || {};
            const stack = createNode("div", "content-stack");

            const hero = createNode("section", "panel hero-panel");
            const heroText = document.createElement("div");
            heroText.append(
                createNode("p", "eyebrow", "Desktop runtime"),
                createNode("h2", "", "Administration console"),
                createNode(
                    "p",
                    "",
                    server.share_hint || "Inspect runtime status, browse the directory, and manage operational features without leaving the embedded server window."
                )
            );
            const heroActions = createNode("div", "panel-actions");
            heroActions.append(
                actionButton("Open site", "button button--primary", () => openBrowser("/")),
                actionButton("Copy URL", "button button--secondary", () => copyText(server.primary_url || server.base_url || ""))
            );
            hero.append(heroText, heroActions);

            const statsGrid = createNode("section", "stats-grid");
            [
                ["Users", stats.users || 0],
                ["Groups", stats.groups || 0],
                ["Exams", stats.exams || 0],
                ["API entries", stats.api_entries || 0]
            ].forEach(([label, value]) => {
                const card = createNode("article", "stat-card");
                card.append(
                    createNode("div", "stat-card__label", label),
                    createNode("div", "stat-card__value", String(value))
                );
                statsGrid.append(card);
            });

            const split = createNode("section", "split-layout");

            const runtimePanel = createNode("article", "panel panel--fill");
            runtimePanel.append(panelHeading("Runtime", "Instance status", "Live network, storage, and runtime metadata."));
            const runtimeBody = createNode("div", "runtime-list panel-scroll");
            [
                ["Primary URL", server.primary_url || "Not available"],
                ["Loopback URL", server.loopback_url || "Not available"],
                ["Data directory", server.data_dir || "Not available"],
                ["Database path", server.db_path || "Not available"],
                ["Media root", server.media_root || "Not available"],
                ["Instance ID", server.instance_id || "Not available"],
                ["Last refresh", server.refresh_label || "Not available"],
                ["Started at", server.started_at_label || "Not available"]
            ].forEach(([label, value]) => {
                const row = createNode("div", "runtime-row");
                row.append(
                    createNode("div", "runtime-row__label", label),
                    createNode("div", "runtime-row__value", value)
                );
                runtimeBody.append(row);
            });
            runtimePanel.append(runtimeBody);

            const accessPanel = createNode("article", "panel panel--fill");
            accessPanel.append(panelHeading("Access", "Reachable endpoints", "Saved aliases are verified against the current Zertan instance."));
            const endpointList = createNode("div", "endpoint-list panel-scroll");
            const endpointItems = [
                {
                    title: server.primary_label || "Primary endpoint",
                    value: server.primary_url || "Not available",
                    status: server.primary_status || server.health_label,
                    helper: server.primary_message || server.share_hint || ""
                },
                {
                    title: "Loopback endpoint",
                    value: server.loopback_url || "Not available",
                    status: "verified",
                    helper: "Use this address locally on the host machine."
                },
                ...((server.aliases || []).map((alias) => ({
                    title: alias.label || alias.host,
                    value: alias.url || "Not available",
                    status: alias.verification_status || "unknown",
                    helper: alias.verification_message || ""
                })))
            ];
            if (!endpointItems.length) {
                endpointList.append(createNode("div", "empty-state", "No endpoints are available."));
            } else {
                endpointItems.forEach((item) => {
                    const card = createNode("article", "endpoint-card");
                    const top = createNode("div", "endpoint-card__top");
                    const copy = document.createElement("div");
                    copy.append(
                        createNode("strong", "", item.title),
                        createNode("p", "", item.helper || "No verification details available.")
                    );
                    top.append(copy, badgeNode(buildBadgeForStatus(item.status), item.status || "unknown"));
                    card.append(
                        top,
                        createNode("div", "endpoint-card__value", item.value)
                    );
                    endpointList.append(card);
                });
            }
            accessPanel.append(endpointList);

            split.append(runtimePanel, accessPanel);
            stack.append(hero, statsGrid, split);
            return stack;
        }

        function buildDirectoryView() {
            const data = snapshot();
            const stack = createNode("div", "content-stack content-stack--two-rows");
            const hero = createNode("section", "panel hero-panel");
            const heroText = document.createElement("div");
            heroText.append(
                createNode("p", "eyebrow", "Directory"),
                createNode("h2", "", "Users and groups"),
                createNode(
                    "p",
                    "",
                    "Search the current domain and inspect results in place. The floating results panel reuses the same overlay treatment used by the client pickers."
                )
            );
            const heroMeta = createNode("div", "hero-meta");
            heroMeta.append(
                badgeNode("badge badge--primary", `${(data.users || []).length} users`),
                badgeNode("badge badge--warning", `${(data.groups || []).length} groups`)
            );
            hero.append(heroText, heroMeta);

            const grid = createNode("section", "directory-grid");

            const searchPanel = createNode("article", "panel panel--fill directory-search-card");
            searchPanel.append(panelHeading("Search", "Directory lookup", "Search by display name, login, role, status, code, or member."));
            const searchBody = createNode("div", "panel-scroll");
            const searchWrap = createNode("div", "directory-search");
            const label = createNode("label", "admin-directory-search");
            const span = createNode("span", "", "Search users or groups");
            const input = document.createElement("input");
            input.id = "directory-search-input";
            input.type = "search";
            input.placeholder = "Search by name, login, role, status, group, or code";
            input.value = state.directoryQuery;
            input.addEventListener("input", (event) => {
                state.directoryQuery = event.target.value;
                openDirectoryPanel();
                renderSearchOverlay();
            });
            input.addEventListener("focus", () => {
                openDirectoryPanel();
                renderSearchOverlay();
            });
            label.append(span, input);
            searchWrap.append(label, createNode("p", "helper", "The results panel floats above the content so the surrounding context stays visible."));
            searchBody.append(searchWrap);

            const quickList = createNode("div", "directory-list");
            const recentUsers = (data.users || []).slice(0, 5);
            if (!recentUsers.length) {
                quickList.append(createNode("div", "empty-state", "No users are available in this domain."));
            } else {
                recentUsers.forEach((user) => {
                    const card = createNode("article", "directory-card");
                    const top = createNode("div", "directory-card__top");
                    const copy = document.createElement("div");
                    copy.append(
                        createNode("strong", "", user.display_name || user.login_name),
                        createNode("p", "", `${user.login_name} · ${user.role} · ${user.status}`)
                    );
                    top.append(copy, actionButton("View", "button button--secondary button--small", () => openModalForEntity("user", user.id)));
                    const meta = createNode("div", "directory-card__meta");
                    meta.append(
                        createNode("span", "", `Groups: ${(user.group_names || []).join(", ") || "No groups"}`),
                        createNode("span", "", `Last login: ${user.last_login_label || "Not available"}`)
                    );
                    card.append(top, meta);
                    quickList.append(card);
                });
            }
            searchBody.append(quickList);
            searchPanel.append(searchBody);

            const groupsPanel = createNode("article", "panel panel--fill");
            groupsPanel.append(panelHeading("Groups", "Scope overview", "These are the currently configured access groups in the domain."));
            const groupsList = createNode("div", "directory-list panel-scroll");
            if (!(data.groups || []).length) {
                groupsList.append(createNode("div", "empty-state", "No groups have been defined yet."));
            } else {
                (data.groups || []).forEach((group) => {
                    const card = createNode("article", "directory-card");
                    const top = createNode("div", "directory-card__top");
                    const copy = document.createElement("div");
                    copy.append(
                        createNode("strong", "", group.name),
                        createNode("p", "", `${group.code} · ${group.member_count} members`)
                    );
                    top.append(copy, actionButton("View", "button button--secondary button--small", () => openModalForEntity("group", group.id)));
                    const meta = createNode("div", "directory-card__meta");
                    meta.append(
                        createNode("span", "", group.description || "No description"),
                        createNode("span", "", `Status: ${group.status}`)
                    );
                    card.append(top, meta);
                    groupsList.append(card);
                });
            }
            groupsPanel.append(groupsList);

            grid.append(searchPanel, groupsPanel);
            stack.append(hero, grid);
            return stack;
        }

        function buildFeaturesView() {
            const data = snapshot();
            const stack = createNode("div", "content-stack content-stack--two-rows");
            const hero = createNode("section", "panel hero-panel");
            const heroText = document.createElement("div");
            heroText.append(
                createNode("p", "eyebrow", "Features"),
                createNode("h2", "", "Operational feature toggles"),
                createNode("p", "", "Flip site capabilities from the embedded server console without opening the browser admin page first.")
            );
            const heroMeta = createNode("div", "hero-meta");
            heroMeta.append(
                badgeNode("badge badge--primary", `${(data.features || []).length} registered`),
                badgeNode("badge badge--ok", `${data.stats && data.stats.enabled_features ? data.stats.enabled_features : 0} enabled`)
            );
            hero.append(heroText, heroMeta);

            const panel = createNode("section", "panel panel--fill");
            panel.append(panelHeading("Feature flags", "Live configuration", "Changes are persisted immediately to the current domain database."));
            const list = createNode("div", "feature-list panel-scroll");
            if (!(data.features || []).length) {
                list.append(createNode("div", "empty-state", "No site features are registered."));
            } else {
                (data.features || []).forEach((feature) => {
                    const row = createNode("label", "feature-toggle-row");
                    const copy = createNode("div", "feature-toggle-row__copy");
                    copy.append(
                        createNode("strong", "", feature.label),
                        createNode("p", "", feature.description || feature.feature_key)
                    );
                    const toggle = createNode("span", "feature-toggle");
                    const input = document.createElement("input");
                    input.type = "checkbox";
                    input.checked = !!feature.enabled;
                    input.disabled = !!state.featureBusy[feature.feature_key];
                    input.addEventListener("change", () => toggleFeature(feature.feature_key, input.checked));
                    const track = createNode("span", "feature-toggle__track");
                    toggle.append(input, track);
                    row.append(copy, toggle);
                    list.append(row);
                });
            }
            panel.append(list);
            stack.append(hero, panel);
            return stack;
        }

        function buildActivityView() {
            const stack = createNode("div", "content-stack content-stack--two-rows");
            const hero = createNode("section", "panel hero-panel");
            const heroText = document.createElement("div");
            heroText.append(
                createNode("p", "eyebrow", "API log"),
                createNode("h2", "", "Important runtime requests"),
                createNode("p", "", "This feed is built from live API traffic captured while the desktop server is running, excluding noisy bulk GET requests.")
            );
            hero.append(heroText);

            const panel = createNode("section", "panel panel--fill");
            panel.append(panelHeading("Runtime feed", "Recent API activity", "Use the filters to focus on write operations or failures."));

            const body = createNode("div", "activity-panel-body");
            const filters = createNode("div", "activity-filters");
            [
                ["all", "All entries"],
                ["write", "Writes"],
                ["errors", "Errors"]
            ].forEach(([value, label]) => {
                const button = createNode("button", `activity-filter${state.activityFilter === value ? " is-active" : ""}`, label);
                button.type = "button";
                button.addEventListener("click", () => {
                    state.activityFilter = value;
                    renderAll();
                });
                filters.append(button);
            });
            body.append(filters);

            const list = createNode("div", "activity-list");
            const items = filterActivityItems();
            if (!items.length) {
                list.append(createNode("div", "empty-state", "No API requests match the current filter."));
            } else {
                items.forEach((item) => {
                    const card = createNode("article", "activity-card");
                    const top = createNode("div", "activity-card__top");
                    const copy = document.createElement("div");
                    copy.append(
                        createNode("strong", "", `${item.method || "API"} ${item.path || ""}`.trim()),
                        createNode("p", "", item.request_body_preview || item.query_string || "No payload or query string.")
                    );
                    const actions = createNode("div", "chip-list");
                    actions.append(
                        badgeNode(buildBadgeForStatus(item.status_family), `${item.status_code || "-"} · ${item.user_label || "Anonymous"}`),
                        badgeNode("badge badge--warning", item.timestamp || "Not available"),
                        actionButton("View", "button button--secondary button--small", () => openActivityModal(item.id))
                    );
                    top.append(copy, actions);
                    const meta = createNode("div", "activity-card__meta");
                    meta.append(
                        createNode("span", "", `Method: ${item.method || "Unknown"}`),
                        createNode("span", "", `Duration: ${item.duration_ms || 0} ms`),
                        createNode("span", "", `From: ${item.remote_addr || "Unknown IP"}`)
                    );
                    card.append(top, meta);
                    list.append(card);
                });
            }

            body.append(list);
            panel.append(body);
            stack.append(hero, panel);
            return stack;
        }

        function panelHeading(label, title, subtitle) {
            const heading = createNode("div", "panel-heading");
            const left = document.createElement("div");
            left.append(
                createNode("div", "panel-label", label),
                createNode("h3", "", title),
                createNode("p", "", subtitle)
            );
            heading.append(left);
            return heading;
        }

        function actionButton(label, className, onClick, disabled) {
            const button = createNode("button", className, label);
            button.type = "button";
            button.disabled = !!disabled;
            button.addEventListener("click", onClick);
            return button;
        }

        function renderMain() {
            const host = document.getElementById("main-content");
            host.innerHTML = "";
            if (state.section === "directory") {
                host.append(buildDirectoryView());
                renderSearchOverlay();
                return;
            }
            closeDirectoryPanel();
            if (state.section === "features") {
                host.append(buildFeaturesView());
                return;
            }
            if (state.section === "activity") {
                host.append(buildActivityView());
                return;
            }
            host.append(buildOverviewView());
        }

        function renderSearchOverlay() {
            const root = document.getElementById("floating-panel-root");
            root.innerHTML = "";
            if (state.section !== "directory" || !state.directoryPanelOpen) {
                return;
            }

            const input = document.getElementById("directory-search-input");
            if (!input) {
                return;
            }

            const bounds = input.getBoundingClientRect();
            const panel = createNode("div", "");
            panel.setAttribute("data-floating-panel", "true");
            panel.style.left = `${Math.max(16, bounds.left)}px`;
            panel.style.top = `${Math.min(window.innerHeight - 360, bounds.bottom + 8)}px`;
            panel.style.width = `${Math.min(580, Math.max(320, bounds.width + 120))}px`;

            const header = createNode("div", "search-overlay-header");
            header.append(
                createNode("strong", "", "Directory results"),
                actionButton("Close", "search-overlay-close", closeDirectoryPanel)
            );
            panel.append(header);

            const list = createNode("div", "admin-picker-results");
            const items = filterDirectoryEntities();
            if (!items.length) {
                list.append(createNode("div", "empty-state", state.directoryQuery.trim() ? "No users or groups match the current search." : "Start typing to search the domain directory."));
            } else {
                items.forEach((item) => {
                    const row = createNode("div", "admin-picker-result");
                    const copy = createNode("div", "admin-picker-result__copy");
                    copy.append(
                        createNode("strong", "", item.title),
                        createNode("p", "", `${item.kind.toUpperCase()} · ${item.helper}`)
                    );
                    const actions = createNode("div", "admin-picker-result__actions");
                    actions.append(
                        actionButton("Inspect", "button button--secondary button--small", () => {
                            closeDirectoryPanel();
                            openEntityModal(item.kind, item.payload);
                        })
                    );
                    row.append(copy, actions);
                    list.append(row);
                });
            }
            panel.append(list);
            root.append(panel);
        }

        function openDirectoryPanel() {
            state.directoryPanelOpen = true;
        }

        function closeDirectoryPanel() {
            state.directoryPanelOpen = false;
            const root = document.getElementById("floating-panel-root");
            if (root) {
                root.innerHTML = "";
            }
        }

        function openModalForEntity(kind, id) {
            const data = snapshot();
            if (kind === "user") {
                const user = (data.users || []).find((entry) => Number(entry.id) === Number(id));
                if (user) {
                    openEntityModal("user", user);
                }
                return;
            }
            const group = (data.groups || []).find((entry) => Number(entry.id) === Number(id));
            if (group) {
                openEntityModal("group", group);
            }
        }

        function openActivityModal(id) {
            const item = (snapshot().activity || []).find((entry) => Number(entry.id) === Number(id));
            if (!item) {
                return;
            }
            openModal({
                eyebrow: "API log",
                title: `${item.method || "API"} ${item.path || ""}`.trim(),
                subtitle: `${item.user_label || "Anonymous"} · ${item.timestamp || "Not available"}`,
                avatar: initialsFromText(item.user_label || "API"),
                meta: [
                    ["Status", `${item.status_code || "-"} · ${item.status_family || "unknown"}`],
                    ["Method", item.method || "Unknown"],
                    ["Duration", `${item.duration_ms || 0} ms`],
                    ["User", item.user_label || "Anonymous"]
                ],
                sections: [
                    buildDetailSection("Summary", [
                        ["Path", item.path || "Not available"],
                        ["Query string", item.query_string || "None"],
                        ["Endpoint", item.endpoint || "Not available"],
                        ["Remote address", item.remote_addr || "Unknown IP"],
                        ["Role", item.user_role || "Unknown"],
                        ["Timestamp", item.timestamp || "Not available"]
                    ]),
                    buildCodeSection("Request payload", item.request_body_preview || "")
                ]
            });
        }

        function openEntityModal(kind, entity) {
            if (kind === "user") {
                openModal({
                    eyebrow: "User",
                    title: entity.display_name || entity.login_name,
                    subtitle: `${entity.login_name} · ${entity.role} · ${entity.status}`,
                    avatar: initialsFromText(entity.display_name || entity.login_name || "User"),
                    meta: [
                        ["Role", entity.role || "Unknown"],
                        ["Status", entity.status || "Unknown"],
                        ["Created", entity.created_at_label || "Not available"],
                        ["Last login", entity.last_login_label || "Not available"]
                    ],
                    sections: [
                        buildDetailSection("Identity", [
                            ["Login name", entity.login_name || "Not available"],
                            ["Protected", entity.is_protected ? "Yes" : "No"],
                            ["Groups", (entity.group_names || []).join(", ") || "No groups assigned"],
                            ["Avatar path", entity.avatar_path || "No avatar"]
                        ])
                    ]
                });
                return;
            }
            openModal({
                eyebrow: "Group",
                title: entity.name || entity.code,
                subtitle: `${entity.code} · ${entity.member_count} members`,
                avatar: initialsFromText(entity.name || entity.code || "Group"),
                meta: [
                    ["Code", entity.code || "Unknown"],
                    ["Status", entity.status || "Unknown"],
                    ["Members", String(entity.member_count || 0)],
                    ["Updated", entity.updated_at || "Not available"]
                ],
                sections: [
                    buildDetailSection("Definition", [
                        ["Description", entity.description || "No description"],
                        ["Members", (entity.members || []).map((member) => `${member.display_name || member.login_name} (${member.role})`).join(", ") || "No members"]
                    ])
                ]
            });
        }

        function buildDetailSection(title, items) {
            return {
                title,
                type: "grid",
                items
            };
        }

        function buildCodeSection(title, value) {
            const rendered = value && typeof value === "object" ? JSON.stringify(value, null, 2) : String(value || "");
            return {
                title,
                type: "code",
                value: rendered || "No data available."
            };
        }

        function openModal(payload) {
            state.modalItem = payload;
            renderModal();
            const modal = document.getElementById("detail-modal");
            modal.hidden = false;
            document.body.classList.add("modal-open");
            requestAnimationFrame(() => {
                modal.dataset.state = "open";
            });
        }

        function closeModal() {
            const modal = document.getElementById("detail-modal");
            if (modal.hidden) {
                return;
            }
            modal.dataset.state = "closing";
            window.setTimeout(() => {
                modal.hidden = true;
                modal.dataset.state = "";
                document.body.classList.remove("modal-open");
            }, 220);
        }

        function renderModal() {
            const payload = state.modalItem;
            if (!payload) {
                return;
            }
            document.getElementById("detail-modal-eyebrow").textContent = payload.eyebrow || "Details";
            document.getElementById("detail-modal-title").textContent = payload.title || "Console detail";
            document.getElementById("detail-modal-subtitle").textContent = payload.subtitle || "";
            document.getElementById("detail-modal-avatar").textContent = payload.avatar || "ZT";

            const metaGrid = document.getElementById("detail-modal-meta-grid");
            metaGrid.innerHTML = "";
            (payload.meta || []).forEach(([label, value]) => {
                const card = createNode("div", "dashboard-modal__meta-card");
                card.append(
                    createNode("span", "detail-inline__label", label),
                    createNode("strong", "", value || "Not available")
                );
                metaGrid.append(card);
            });

            const sections = document.getElementById("detail-modal-sections");
            sections.innerHTML = "";
            (payload.sections || []).forEach((section) => {
                const block = createNode("section", "detail-block");
                block.append(createNode("h3", "", section.title || "Details"));
                if (section.type === "code") {
                    const pre = document.createElement("pre");
                    pre.textContent = section.value || "No data available.";
                    block.append(pre);
                } else {
                    const grid = createNode("div", "detail-inline-grid");
                    (section.items || []).forEach(([label, value]) => {
                        const row = createNode("div", "detail-inline");
                        row.append(
                            createNode("div", "detail-inline__label", label),
                            createNode("div", "detail-inline__value", value || "Not available")
                        );
                        grid.append(row);
                    });
                    block.append(grid);
                }
                sections.append(block);
            });
        }

        function initialsFromText(value) {
            const cleaned = String(value || "").trim();
            if (!cleaned) {
                return "ZT";
            }
            const parts = cleaned.split(/\s+/).filter(Boolean).slice(0, 2);
            if (!parts.length) {
                return cleaned.slice(0, 2).toUpperCase();
            }
            return parts.map((part) => part[0]).join("").slice(0, 2).toUpperCase();
        }

        async function refreshSnapshot() {
            const bridge = api();
            if (!bridge || typeof bridge.refresh_console !== "function") {
                return;
            }
            try {
                state.snapshot = await bridge.refresh_console();
                renderAll();
            } catch (error) {
                console.error("Unable to refresh server console state", error);
            }
        }

        async function toggleFeature(featureKey, enabled) {
            const bridge = api();
            if (!bridge || typeof bridge.toggle_feature !== "function") {
                return;
            }
            state.featureBusy[featureKey] = true;
            renderAll();
            try {
                const response = await bridge.toggle_feature(featureKey, enabled);
                if (response && response.snapshot) {
                    state.snapshot = response.snapshot;
                }
            } catch (error) {
                console.error("Unable to toggle feature", error);
            } finally {
                delete state.featureBusy[featureKey];
                renderAll();
            }
        }

        async function openBrowser(path) {
            const bridge = api();
            if (!bridge || typeof bridge.open_browser !== "function") {
                return;
            }
            try {
                await bridge.open_browser(path || "/");
            } catch (error) {
                console.error("Unable to open browser", error);
            }
        }

        async function requestShutdown() {
            const bridge = api();
            if (!bridge || typeof bridge.request_shutdown !== "function" || state.stopping) {
                return;
            }
            state.stopping = true;
            renderAll();
            try {
                await bridge.request_shutdown();
            } catch (error) {
                console.error("Unable to stop server", error);
                state.stopping = false;
                renderAll();
            }
        }

        async function copyText(value) {
            const text = String(value || "").trim();
            if (!text) {
                return;
            }
            try {
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    await navigator.clipboard.writeText(text);
                    return;
                }
            } catch (error) {
                console.warn("Clipboard API unavailable", error);
            }

            const helper = document.createElement("textarea");
            helper.value = text;
            helper.style.position = "fixed";
            helper.style.opacity = "0";
            document.body.append(helper);
            helper.focus();
            helper.select();
            try {
                document.execCommand("copy");
            } finally {
                helper.remove();
            }
        }

        function bindGlobalEvents() {
            const navToggle = document.getElementById("nav-toggle");
            const navMenu = document.getElementById("nav-menu");
            if (navToggle && navMenu) {
                const toggleMenu = (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    state.navOpen = !state.navOpen;
                    syncNavMenuState();
                };
                navToggle.addEventListener("click", toggleMenu);
                navMenu.addEventListener("click", (event) => {
                    event.stopPropagation();
                });
            }
            document.getElementById("detail-modal-close").addEventListener("click", closeModal);
            document.getElementById("detail-modal-backdrop").addEventListener("click", closeModal);
            document.addEventListener("click", (event) => {
                const toggle = document.getElementById("nav-toggle");
                const menu = document.getElementById("nav-menu");
                const clickedToggle = toggle && toggle.contains(event.target);
                const clickedMenu = menu && menu.contains(event.target);
                if (state.navOpen && !clickedToggle && !clickedMenu) {
                    closeNavMenu();
                }

                const input = document.getElementById("directory-search-input");
                const root = document.getElementById("floating-panel-root");
                if (!input || state.section !== "directory" || !state.directoryPanelOpen) {
                    return;
                }
                const panel = root.querySelector('[data-floating-panel="true"]');
                const clickedInsideInput = input.contains(event.target);
                const clickedInsidePanel = panel && panel.contains(event.target);
                if (!clickedInsideInput && !clickedInsidePanel) {
                    closeDirectoryPanel();
                }
            });
            window.addEventListener("resize", () => {
                closeNavMenu();
                syncResponsiveHeaderMetrics();
                if (state.directoryPanelOpen) {
                    renderSearchOverlay();
                }
            });
            document.addEventListener("keydown", (event) => {
                if (event.key === "Escape") {
                    closeModal();
                    closeDirectoryPanel();
                    closeNavMenu();
                }
            });
        }

        function renderAll() {
            renderSidebar();
            renderNav();
            renderMain();
            syncNavMenuState();
            requestAnimationFrame(syncResponsiveHeaderMetrics);
        }

        function startRefreshLoop() {
            if (refreshTimer) {
                window.clearInterval(refreshTimer);
            }
            refreshTimer = window.setInterval(refreshSnapshot, 1000);
        }

        function initialize() {
            if (initialized) {
                renderAll();
                return;
            }
            initialized = true;
            bindGlobalEvents();
            renderAll();
            startRefreshLoop();
        }

        window.addEventListener("pywebviewready", async () => {
            const bridge = api();
            if (bridge && typeof bridge.get_console_snapshot === "function") {
                try {
                    state.snapshot = await bridge.get_console_snapshot();
                } catch (error) {
                    console.error("Unable to load initial bridge state", error);
                }
            }
            initialize();
        });

        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", () => {
                if (!api()) {
                    initialize();
                }
            });
        } else if (!api()) {
            initialize();
        }
