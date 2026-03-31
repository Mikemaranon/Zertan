(function (App) {
    App.renderSidebar = function () {
        const data = App.snapshot();
        const server = data.server || {};
        const stats = data.stats || {};

        const badges = document.getElementById("sidebar-badges");
        badges.innerHTML = "";
        badges.append(
            App.badgeNode(App.buildBadgeForStatus(server.health_label), server.health_label || "Unknown"),
            App.badgeNode("badge badge--primary", `Port ${server.port || "-"}`),
            App.badgeNode("badge badge--warning", `${server.uptime_label || "00h 00m"}`),
            App.badgeNode("badge badge--primary", `${stats.active_sessions || 0} sessions`)
        );
    };

    App.syncResponsiveHeaderMetrics = function () {
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
    };

    App.renderNav = function () {
        const desktopNode = document.getElementById("nav-list-desktop");
        const mobileNode = document.getElementById("nav-list-mobile");
        [desktopNode, mobileNode].forEach((node) => {
            if (!node) {
                return;
            }
            node.innerHTML = "";
            App.NAV_SECTIONS.forEach((section) => {
                const button = App.createNode("button", `nav-button${App.state.section === section.id ? " is-active" : ""}`);
                button.type = "button";
                button.append(
                    App.createNode("span", "nav-button__title", section.label),
                    App.createNode("span", "nav-button__helper", section.helper)
                );
                button.addEventListener("click", () => {
                    App.state.section = section.id;
                    if (section.id !== "directory") {
                        App.closeDirectoryPanel();
                    }
                    App.closeNavMenu();
                    App.renderAll();
                });
                node.append(button);
            });
        });
    };

    App.syncNavMenuState = function () {
        const menu = document.getElementById("nav-menu");
        const toggle = document.getElementById("nav-toggle");
        const isMobile = window.innerWidth <= 1100;
        const shouldOpen = !!App.state.navOpen && isMobile;
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
        requestAnimationFrame(App.syncResponsiveHeaderMetrics);
    };

    App.closeNavMenu = function () {
        if (!App.state.navOpen) {
            App.syncNavMenuState();
            return;
        }
        App.state.navOpen = false;
        App.syncNavMenuState();
    };
})(window.ServerConsole);
