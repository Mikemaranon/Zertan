(function (App) {
    App.filterActivityItems = function () {
        const items = App.snapshot().activity || [];
        if (App.state.activityFilter === "all") {
            return items;
        }
        if (App.state.activityFilter === "write") {
            return items.filter((item) => String(item.method || "").toUpperCase() !== "GET");
        }
        if (App.state.activityFilter === "errors") {
            return items.filter((item) => Number(item.status_code || 0) >= 400);
        }
        return items;
    };

    App.buildActivityView = function () {
        const stack = App.createNode("div", "content-stack content-stack--two-rows");
        const hero = App.createNode("section", "panel hero-panel");
        const heroText = document.createElement("div");
        heroText.append(
            App.createNode("p", "eyebrow", "API log"),
            App.createNode("h2", "", "Important runtime requests"),
            App.createNode("p", "", "This feed is built from live API traffic captured while the desktop server is running, excluding noisy bulk GET requests.")
        );
        hero.append(heroText);

        const panel = App.createNode("section", "panel panel--fill");
        panel.append(App.panelHeading("Runtime feed", "Recent API activity", "Use the filters to focus on write operations or failures."));

        const body = App.createNode("div", "activity-panel-body");
        const filters = App.createNode("div", "activity-filters");
        [
            ["all", "All entries"],
            ["write", "Writes"],
            ["errors", "Errors"]
        ].forEach(([value, label]) => {
            const button = App.createNode("button", `activity-filter${App.state.activityFilter === value ? " is-active" : ""}`, label);
            button.type = "button";
            button.addEventListener("click", () => {
                App.state.activityFilter = value;
                App.renderAll();
            });
            filters.append(button);
        });
        body.append(filters);

        const list = App.createNode("div", "activity-list");
        list.dataset.scrollKey = "activity-list";
        const items = App.filterActivityItems();
        if (!items.length) {
            list.append(App.createNode("div", "empty-state", "No API requests match the current filter."));
        } else {
            items.forEach((item) => {
                const card = App.createNode("article", "activity-card");
                card.dataset.activityId = String(item.id || "");
                const top = App.createNode("div", "activity-card__top");
                const copy = document.createElement("div");
                copy.append(
                    App.createNode("strong", "", `${item.method || "API"} ${item.path || ""}`.trim()),
                    App.createNode("p", "", item.request_body_preview || item.query_string || "No payload or query string.")
                );
                const actions = App.createNode("div", "chip-list");
                actions.append(
                    App.badgeNode(App.buildBadgeForStatus(item.status_family), `${item.status_code || "-"} · ${item.user_label || "Anonymous"}`),
                    App.badgeNode("badge badge--warning", item.timestamp || "Not available"),
                    App.actionButton("View", "button button--secondary button--small", () => App.openActivityModal(item.id))
                );
                top.append(copy, actions);
                const meta = App.createNode("div", "activity-card__meta");
                meta.append(
                    App.createNode("span", "", `Method: ${item.method || "Unknown"}`),
                    App.createNode("span", "", `Duration: ${item.duration_ms || 0} ms`),
                    App.createNode("span", "", `From: ${item.remote_addr || "Unknown IP"}`)
                );
                card.append(top, meta);
                list.append(card);
            });
        }

        body.append(list);
        panel.append(body);
        stack.append(hero, panel);
        return stack;
    };
})(window.ServerConsole);
