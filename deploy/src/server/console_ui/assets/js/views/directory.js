(function (App) {
    App.buildDirectoryView = function () {
        const data = App.snapshot();
        const stack = App.createNode("div", "content-stack content-stack--two-rows");
        const hero = App.createNode("section", "panel hero-panel");
        const heroText = document.createElement("div");
        heroText.append(
            App.createNode("p", "eyebrow", "Directory"),
            App.createNode("h2", "", "Users and groups"),
            App.createNode(
                "p",
                "",
                "Search the current domain and inspect results in place. The floating results panel reuses the same overlay treatment used by the client pickers."
            )
        );
        const heroMeta = App.createNode("div", "hero-meta");
        heroMeta.append(
            App.badgeNode("badge badge--primary", `${(data.users || []).length} users`),
            App.badgeNode("badge badge--warning", `${(data.groups || []).length} groups`)
        );
        hero.append(heroText, heroMeta);

        const grid = App.createNode("section", "directory-grid");

        const searchPanel = App.createNode("article", "panel panel--fill directory-search-card");
        searchPanel.append(App.panelHeading("Search", "Directory lookup", "Search by display name, login, role, status, code, or member."));
        const searchBody = App.createNode("div", "panel-scroll");
        const searchWrap = App.createNode("div", "directory-search");
        const label = App.createNode("label", "admin-directory-search");
        const span = App.createNode("span", "", "Search users or groups");
        const input = document.createElement("input");
        input.id = "directory-search-input";
        input.type = "search";
        input.placeholder = "Search by name, login, role, status, group, or code";
        input.value = App.state.directoryQuery;
        input.addEventListener("input", (event) => {
            App.state.directoryQuery = event.target.value;
            App.openDirectoryPanel();
            App.renderSearchOverlay();
        });
        input.addEventListener("focus", () => {
            App.openDirectoryPanel();
            App.renderSearchOverlay();
        });
        label.append(span, input);
        searchWrap.append(label, App.createNode("p", "helper", "The results panel floats above the content so the surrounding context stays visible."));
        searchBody.append(searchWrap);

        const quickList = App.createNode("div", "directory-list");
        const recentUsers = (data.users || []).slice(0, 5);
        if (!recentUsers.length) {
            quickList.append(App.createNode("div", "empty-state", "No users are available in this domain."));
        } else {
            recentUsers.forEach((user) => {
                const card = App.createNode("article", "directory-card");
                const top = App.createNode("div", "directory-card__top");
                const copy = document.createElement("div");
                copy.append(
                    App.createNode("strong", "", user.display_name || user.login_name),
                    App.createNode("p", "", `${user.login_name} · ${user.role} · ${user.status}`)
                );
                top.append(copy, App.actionButton("View", "button button--secondary button--small", () => App.openModalForEntity("user", user.id)));
                const meta = App.createNode("div", "directory-card__meta");
                meta.append(
                    App.createNode("span", "", `Groups: ${(user.group_names || []).join(", ") || "No groups"}`),
                    App.createNode("span", "", `Last login: ${user.last_login_label || "Not available"}`)
                );
                card.append(top, meta);
                quickList.append(card);
            });
        }
        searchBody.append(quickList);
        searchPanel.append(searchBody);

        const groupsPanel = App.createNode("article", "panel panel--fill");
        groupsPanel.append(App.panelHeading("Groups", "Scope overview", "These are the currently configured access groups in the domain."));
        const groupsList = App.createNode("div", "directory-list panel-scroll");
        if (!(data.groups || []).length) {
            groupsList.append(App.createNode("div", "empty-state", "No groups have been defined yet."));
        } else {
            (data.groups || []).forEach((group) => {
                const card = App.createNode("article", "directory-card");
                const top = App.createNode("div", "directory-card__top");
                const copy = document.createElement("div");
                copy.append(
                    App.createNode("strong", "", group.name),
                    App.createNode("p", "", `${group.code} · ${group.member_count} members`)
                );
                top.append(copy, App.actionButton("View", "button button--secondary button--small", () => App.openModalForEntity("group", group.id)));
                const meta = App.createNode("div", "directory-card__meta");
                meta.append(
                    App.createNode("span", "", group.description || "No description"),
                    App.createNode("span", "", `Status: ${group.status}`)
                );
                card.append(top, meta);
                groupsList.append(card);
            });
        }
        groupsPanel.append(groupsList);

        grid.append(searchPanel, groupsPanel);
        stack.append(hero, grid);
        return stack;
    };
})(window.ServerConsole);
