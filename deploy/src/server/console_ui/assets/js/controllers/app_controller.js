(function (App) {
    App.bindThemeControls = function () {
        document.querySelectorAll("[data-server-console-theme-select]").forEach((select) => {
            if (select.dataset.themeBound === "true") {
                return;
            }

            select.dataset.themeBound = "true";
            select.addEventListener("change", () => {
                App.applyTheme(select.value);
                App.syncThemeSelects();
            });
        });

        App.syncThemeSelects();
    };

    App.renderMain = function () {
        const options = arguments[0] || {};
        const host = document.getElementById("main-content");
        const shouldRender = !!options.force || App.runtime.renderedSection !== App.state.section || !host.firstChild;
        if (!shouldRender) {
            return;
        }

        const scrollState = options.preserveScroll ? App.captureScrollState(host) : null;
        const activityState = options.preserveActivityAnchor ? App.captureActivityListState(host) : null;
        host.innerHTML = "";
        if (App.state.section === "directory") {
            host.append(App.buildDirectoryView());
            App.renderSearchOverlay();
            App.runtime.renderedSection = App.state.section;
            return;
        }
        App.closeDirectoryPanel();
        if (App.state.section === "features") {
            host.append(App.buildFeaturesView());
        } else if (App.state.section === "activity") {
            host.append(App.buildActivityView());
        } else {
            host.append(App.buildOverviewView());
        }
        App.runtime.renderedSection = App.state.section;

        if (scrollState) {
            App.restoreScrollState(host, scrollState);
        }
        if (activityState) {
            App.restoreActivityListState(host, activityState);
        }
    };

    App.captureScrollState = function (root) {
        return Array.from(root.querySelectorAll("[data-scroll-key]")).map((node) => ({
            key: node.dataset.scrollKey,
            scrollTop: node.scrollTop,
            scrollLeft: node.scrollLeft
        }));
    };

    App.restoreScrollState = function (root, entries) {
        (entries || []).forEach((entry) => {
            const node = root.querySelector(`[data-scroll-key="${entry.key}"]`);
            if (!node) {
                return;
            }
            node.scrollTop = entry.scrollTop;
            node.scrollLeft = entry.scrollLeft;
        });
    };

    App.captureActivityListState = function (root) {
        const list = root.querySelector('[data-scroll-key="activity-list"]');
        if (!list) {
            return null;
        }
        if (list.scrollTop <= 4) {
            return { pinnedTop: true };
        }

        const listRect = list.getBoundingClientRect();
        const anchor = Array.from(list.querySelectorAll("[data-activity-id]")).find((node) => {
            const rect = node.getBoundingClientRect();
            return rect.bottom > listRect.top;
        });
        if (!anchor) {
            return {
                pinnedTop: false,
                scrollTop: list.scrollTop
            };
        }

        return {
            pinnedTop: false,
            anchorId: anchor.dataset.activityId,
            offsetTop: anchor.getBoundingClientRect().top - listRect.top,
            scrollTop: list.scrollTop
        };
    };

    App.restoreActivityListState = function (root, state) {
        const list = root.querySelector('[data-scroll-key="activity-list"]');
        if (!list || !state) {
            return;
        }
        if (state.pinnedTop) {
            list.scrollTop = 0;
            return;
        }

        const anchor = state.anchorId ? list.querySelector(`[data-activity-id="${state.anchorId}"]`) : null;
        if (!anchor) {
            list.scrollTop = state.scrollTop || 0;
            return;
        }
        list.scrollTop = Math.max(0, anchor.offsetTop - (state.offsetTop || 0));
    };

    App.refreshLiveRegions = function () {
        App.renderSidebar();
        if (App.state.section === "directory") {
            if (App.state.directoryPanelOpen) {
                App.renderSearchOverlay();
            }
            return;
        }
        App.renderMain({
            force: true,
            preserveScroll: true,
            preserveActivityAnchor: App.state.section === "activity"
        });
    };

    App.refreshSnapshot = async function () {
        const bridge = App.api();
        if (!bridge || typeof bridge.refresh_console !== "function" || App.runtime.refreshInFlight) {
            return;
        }
        App.runtime.refreshInFlight = true;
        try {
            App.state.snapshot = await bridge.refresh_console();
            App.refreshLiveRegions();
        } catch (error) {
            console.error("Unable to refresh server console state", error);
        } finally {
            App.runtime.refreshInFlight = false;
        }
    };

    App.toggleFeature = async function (featureKey, enabled) {
        const bridge = App.api();
        if (!bridge || typeof bridge.toggle_feature !== "function") {
            return;
        }
        App.state.featureBusy[featureKey] = true;
        App.renderAll();
        try {
            const response = await bridge.toggle_feature(featureKey, enabled);
            if (response && response.snapshot) {
                App.state.snapshot = response.snapshot;
            }
        } catch (error) {
            console.error("Unable to toggle feature", error);
        } finally {
            delete App.state.featureBusy[featureKey];
            App.renderAll();
        }
    };

    App.openBrowser = async function (path) {
        const bridge = App.api();
        if (!bridge || typeof bridge.open_browser !== "function") {
            return;
        }
        try {
            await bridge.open_browser(path || "/");
        } catch (error) {
            console.error("Unable to open browser", error);
        }
    };

    App.requestShutdown = async function () {
        const bridge = App.api();
        if (!bridge || typeof bridge.request_shutdown !== "function" || App.state.stopping) {
            return;
        }
        App.state.stopping = true;
        App.renderAll();
        try {
            await bridge.request_shutdown();
        } catch (error) {
            console.error("Unable to stop server", error);
            App.state.stopping = false;
            App.renderAll();
        }
    };

    App.copyText = async function (value) {
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
    };

    App.bindGlobalEvents = function () {
        const navToggle = document.getElementById("nav-toggle");
        const navMenu = document.getElementById("nav-menu");
        if (navToggle && navMenu) {
            const toggleMenu = (event) => {
                event.preventDefault();
                event.stopPropagation();
                App.state.navOpen = !App.state.navOpen;
                App.syncNavMenuState();
            };
            navToggle.addEventListener("click", toggleMenu);
            navMenu.addEventListener("click", (event) => {
                event.stopPropagation();
            });
        }
        document.getElementById("detail-modal-close").addEventListener("click", App.closeModal);
        document.getElementById("detail-modal-backdrop").addEventListener("click", App.closeModal);
        document.addEventListener("click", (event) => {
            const toggle = document.getElementById("nav-toggle");
            const menu = document.getElementById("nav-menu");
            const clickedToggle = toggle && toggle.contains(event.target);
            const clickedMenu = menu && menu.contains(event.target);
            if (App.state.navOpen && !clickedToggle && !clickedMenu) {
                App.closeNavMenu();
            }

            const input = document.getElementById("directory-search-input");
            const root = document.getElementById("floating-panel-root");
            if (!input || App.state.section !== "directory" || !App.state.directoryPanelOpen) {
                return;
            }
            const panel = root.querySelector('[data-floating-panel="true"]');
            const clickedInsideInput = input.contains(event.target);
            const clickedInsidePanel = panel && panel.contains(event.target);
            if (!clickedInsideInput && !clickedInsidePanel) {
                App.closeDirectoryPanel();
            }
        });
        window.addEventListener("resize", () => {
            App.closeNavMenu();
            App.syncResponsiveHeaderMetrics();
            if (App.state.directoryPanelOpen) {
                App.renderSearchOverlay();
            }
        });
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                App.closeModal();
                App.closeDirectoryPanel();
                App.closeNavMenu();
            }
        });
    };

    App.renderAll = function () {
        App.syncThemeSelects();
        App.renderSidebar();
        App.renderNav();
        App.renderMain({ force: true });
        App.syncNavMenuState();
        requestAnimationFrame(App.syncResponsiveHeaderMetrics);
    };

    App.startRefreshLoop = function () {
        if (App.runtime.refreshTimer) {
            window.clearInterval(App.runtime.refreshTimer);
        }
        App.runtime.refreshTimer = window.setInterval(App.refreshSnapshot, 1000);
    };

    App.initialize = function () {
        if (App.runtime.initialized) {
            App.renderAll();
            return;
        }
        App.runtime.initialized = true;
        App.applyTheme(App.state.theme, { persist: false });
        App.bindThemeControls();
        App.bindGlobalEvents();
        App.renderAll();
        App.startRefreshLoop();
    };
})(window.ServerConsole);
