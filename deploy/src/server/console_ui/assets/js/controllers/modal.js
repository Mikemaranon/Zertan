(function (App) {
    App.openActivityModal = function (id) {
        const item = (App.snapshot().activity || []).find((entry) => Number(entry.id) === Number(id));
        if (!item) {
            return;
        }
        App.openModal({
            eyebrow: "API log",
            title: `${item.method || "API"} ${item.path || ""}`.trim(),
            subtitle: `${item.user_label || "Anonymous"} · ${item.timestamp || "Not available"}`,
            avatar: App.initialsFromText(item.user_label || "API"),
            meta: [
                ["Status", `${item.status_code || "-"} · ${item.status_family || "unknown"}`],
                ["Method", item.method || "Unknown"],
                ["Duration", `${item.duration_ms || 0} ms`],
                ["User", item.user_label || "Anonymous"]
            ],
            sections: [
                App.buildDetailSection("Summary", [
                    ["Path", item.path || "Not available"],
                    ["Query string", item.query_string || "None"],
                    ["Endpoint", item.endpoint || "Not available"],
                    ["Remote address", item.remote_addr || "Unknown IP"],
                    ["Role", item.user_role || "Unknown"],
                    ["Timestamp", item.timestamp || "Not available"]
                ]),
                App.buildCodeSection("Request payload", item.request_body_preview || "")
            ]
        });
    };

    App.openEntityModal = function (kind, entity) {
        if (kind === "user") {
            App.openModal({
                eyebrow: "User",
                title: entity.display_name || entity.login_name,
                subtitle: `${entity.login_name} · ${entity.role} · ${entity.status}`,
                avatar: App.initialsFromText(entity.display_name || entity.login_name || "User"),
                meta: [
                    ["Role", entity.role || "Unknown"],
                    ["Status", entity.status || "Unknown"],
                    ["Created", entity.created_at_label || "Not available"],
                    ["Last login", entity.last_login_label || "Not available"]
                ],
                sections: [
                    App.buildDetailSection("Identity", [
                        ["Login name", entity.login_name || "Not available"],
                        ["Protected", entity.is_protected ? "Yes" : "No"],
                        ["Groups", (entity.group_names || []).join(", ") || "No groups assigned"],
                        ["Avatar path", entity.avatar_path || "No avatar"]
                    ])
                ]
            });
            return;
        }
        App.openModal({
            eyebrow: "Group",
            title: entity.name || entity.code,
            subtitle: `${entity.code} · ${entity.member_count} members`,
            avatar: App.initialsFromText(entity.name || entity.code || "Group"),
            meta: [
                ["Code", entity.code || "Unknown"],
                ["Status", entity.status || "Unknown"],
                ["Members", String(entity.member_count || 0)],
                ["Updated", entity.updated_at || "Not available"]
            ],
            sections: [
                App.buildDetailSection("Definition", [
                    ["Description", entity.description || "No description"],
                    ["Members", (entity.members || []).map((member) => `${member.display_name || member.login_name} (${member.role})`).join(", ") || "No members"]
                ])
            ]
        });
    };

    App.openModal = function (payload) {
        App.state.modalItem = payload;
        App.renderModal();
        const modal = document.getElementById("detail-modal");
        modal.hidden = false;
        document.body.classList.add("modal-open");
        requestAnimationFrame(() => {
            modal.dataset.state = "open";
        });
    };

    App.closeModal = function () {
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
    };

    App.renderModal = function () {
        const payload = App.state.modalItem;
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
            const card = App.createNode("div", "dashboard-modal__meta-card");
            card.append(
                App.createNode("span", "detail-inline__label", label),
                App.createNode("strong", "", value || "Not available")
            );
            metaGrid.append(card);
        });

        const sections = document.getElementById("detail-modal-sections");
        sections.innerHTML = "";
        (payload.sections || []).forEach((section) => {
            const block = App.createNode("section", "detail-block");
            block.append(App.createNode("h3", "", section.title || "Details"));
            if (section.type === "code") {
                const pre = document.createElement("pre");
                pre.textContent = section.value || "No data available.";
                block.append(pre);
            } else {
                const grid = App.createNode("div", "detail-inline-grid");
                (section.items || []).forEach(([label, value]) => {
                    const row = App.createNode("div", "detail-inline");
                    row.append(
                        App.createNode("div", "detail-inline__label", label),
                        App.createNode("div", "detail-inline__value", value || "Not available")
                    );
                    grid.append(row);
                });
                block.append(grid);
            }
            sections.append(block);
        });
    };
})(window.ServerConsole);
