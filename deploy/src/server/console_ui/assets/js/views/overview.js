(function (App) {
    App.buildOverviewView = function () {
        const data = App.snapshot();
        const server = data.server || {};
        const stats = data.stats || {};
        const stack = App.createNode("div", "content-stack");

        const hero = App.createNode("section", "panel hero-panel");
        const heroText = document.createElement("div");
        heroText.append(
            App.createNode("p", "eyebrow", "Desktop runtime"),
            App.createNode("h2", "", "Administration console"),
            App.createNode(
                "p",
                "",
                server.share_hint || "Inspect runtime status, browse the directory, and manage operational features without leaving the embedded server window."
            )
        );
        const heroActions = App.createNode("div", "panel-actions");
        heroActions.append(
            App.actionButton("Open site", "button button--primary", () => App.openBrowser("/")),
            App.actionButton("Copy URL", "button button--secondary", () => App.copyText(server.primary_url || server.base_url || ""))
        );
        hero.append(heroText, heroActions);

        const statsGrid = App.createNode("section", "stats-grid");
        [
            ["Users", stats.users || 0],
            ["Groups", stats.groups || 0],
            ["Exams", stats.exams || 0],
            ["API entries", stats.api_entries || 0]
        ].forEach(([label, value]) => {
            const card = App.createNode("article", "stat-card");
            card.append(
                App.createNode("div", "stat-card__label", label),
                App.createNode("div", "stat-card__value", String(value))
            );
            statsGrid.append(card);
        });

        const split = App.createNode("section", "split-layout");

        const runtimePanel = App.createNode("article", "panel panel--fill");
        runtimePanel.append(App.panelHeading("Runtime", "Instance status", "Live network, storage, and runtime metadata."));
        const runtimeBody = App.createNode("div", "runtime-list panel-scroll");
        runtimeBody.dataset.scrollKey = "overview-runtime";
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
            const row = App.createNode("div", "runtime-row");
            row.append(
                App.createNode("div", "runtime-row__label", label),
                App.createNode("div", "runtime-row__value", value)
            );
            runtimeBody.append(row);
        });
        runtimePanel.append(runtimeBody);

        const accessPanel = App.createNode("article", "panel panel--fill");
        accessPanel.append(App.panelHeading("Access", "Reachable endpoints", "Saved aliases are verified against the current Zertan instance."));
        const endpointList = App.createNode("div", "endpoint-list panel-scroll");
        endpointList.dataset.scrollKey = "overview-access";
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
            endpointList.append(App.createNode("div", "empty-state", "No endpoints are available."));
        } else {
            endpointItems.forEach((item) => {
                const card = App.createNode("article", "endpoint-card");
                const top = App.createNode("div", "endpoint-card__top");
                const copy = document.createElement("div");
                copy.append(
                    App.createNode("strong", "", item.title),
                    App.createNode("p", "", item.helper || "No verification details available.")
                );
                top.append(copy, App.badgeNode(App.buildBadgeForStatus(item.status), item.status || "unknown"));
                card.append(
                    top,
                    App.createNode("div", "endpoint-card__value", item.value)
                );
                endpointList.append(card);
            });
        }
        accessPanel.append(endpointList);

        split.append(runtimePanel, accessPanel);
        stack.append(hero, statsGrid, split);
        return stack;
    };
})(window.ServerConsole);
