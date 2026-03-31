(function (App) {
    App.directoryEntities = function () {
        const data = App.snapshot();
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
    };

    App.filterDirectoryEntities = function () {
        const query = App.state.directoryQuery.trim().toLowerCase();
        const entities = App.directoryEntities();
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
    };

    App.renderSearchOverlay = function () {
        const root = document.getElementById("floating-panel-root");
        root.innerHTML = "";
        if (App.state.section !== "directory" || !App.state.directoryPanelOpen) {
            return;
        }

        const input = document.getElementById("directory-search-input");
        if (!input) {
            return;
        }

        const bounds = input.getBoundingClientRect();
        const panel = App.createNode("div", "");
        panel.setAttribute("data-floating-panel", "true");
        panel.style.left = `${Math.max(16, bounds.left)}px`;
        panel.style.top = `${Math.min(window.innerHeight - 360, bounds.bottom + 8)}px`;
        panel.style.width = `${Math.min(580, Math.max(320, bounds.width + 120))}px`;

        const header = App.createNode("div", "search-overlay-header");
        header.append(
            App.createNode("strong", "", "Directory results"),
            App.actionButton("Close", "search-overlay-close", App.closeDirectoryPanel)
        );
        panel.append(header);

        const list = App.createNode("div", "admin-picker-results");
        const items = App.filterDirectoryEntities();
        if (!items.length) {
            list.append(App.createNode(
                "div",
                "empty-state",
                App.state.directoryQuery.trim()
                    ? "No users or groups match the current search."
                    : "Start typing to search the domain directory."
            ));
        } else {
            items.forEach((item) => {
                const row = App.createNode("div", "admin-picker-result");
                const copy = App.createNode("div", "admin-picker-result__copy");
                copy.append(
                    App.createNode("strong", "", item.title),
                    App.createNode("p", "", `${item.kind.toUpperCase()} · ${item.helper}`)
                );
                const actions = App.createNode("div", "admin-picker-result__actions");
                actions.append(
                    App.actionButton("Inspect", "button button--secondary button--small", () => {
                        App.closeDirectoryPanel();
                        App.openEntityModal(item.kind, item.payload);
                    })
                );
                row.append(copy, actions);
                list.append(row);
            });
        }
        panel.append(list);
        root.append(panel);
    };

    App.openDirectoryPanel = function () {
        App.state.directoryPanelOpen = true;
    };

    App.closeDirectoryPanel = function () {
        App.state.directoryPanelOpen = false;
        const root = document.getElementById("floating-panel-root");
        if (root) {
            root.innerHTML = "";
        }
    };

    App.openModalForEntity = function (kind, id) {
        const data = App.snapshot();
        if (kind === "user") {
            const user = (data.users || []).find((entry) => Number(entry.id) === Number(id));
            if (user) {
                App.openEntityModal("user", user);
            }
            return;
        }
        const group = (data.groups || []).find((entry) => Number(entry.id) === Number(id));
        if (group) {
            App.openEntityModal("group", group);
        }
    };
})(window.ServerConsole);
