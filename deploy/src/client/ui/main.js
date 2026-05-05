(function () {
    const invoke = window.__TAURI__.core.invoke;
    const THEMES = new Set(["light", "dark", "graphite", "sage", "north-sea"]);

    const state = {
        busyServerId: "",
        servers: [],
        theme: "light",
    };

    const nodes = {
        list: document.getElementById("server-list"),
        pageError: document.getElementById("server-error"),
        status: document.getElementById("status-message"),
        modal: document.getElementById("server-modal"),
        modalBackdrop: document.getElementById("server-modal-backdrop"),
        modalClose: document.getElementById("server-modal-close"),
        modalCancel: document.getElementById("server-modal-cancel"),
        openModal: document.getElementById("open-server-modal"),
        form: document.getElementById("server-form"),
        modalError: document.getElementById("server-modal-error"),
        name: document.getElementById("server-name"),
        host: document.getElementById("server-host"),
        port: document.getElementById("server-port"),
        themeSelect: document.getElementById("client-theme-select"),
    };

    document.addEventListener("DOMContentLoaded", async () => {
        bindThemeSelect();
        bindModal();
        bindForm();
        bindListActions();
        bindExternalLinks();
        bindThemeRefresh();
        await loadTheme();
        await loadServers();
    });

    function bindThemeSelect() {
        if (!nodes.themeSelect) {
            return;
        }

        nodes.themeSelect.addEventListener("change", async () => {
            clearErrors();
            setStatus("Saving theme...");
            try {
                const theme = normalizeTheme(await invoke("set_client_theme", { theme: nodes.themeSelect.value }));
                applyTheme(theme);
                setStatus("Theme saved.");
            } catch (error) {
                applyTheme(state.theme);
                showPageError(String(error));
                clearStatus();
            }
        });
    }

    function bindThemeRefresh() {
        window.addEventListener("focus", () => {
            void loadTheme();
        });

        document.addEventListener("visibilitychange", () => {
            if (!document.hidden) {
                void loadTheme();
            }
        });
    }

    function bindModal() {
        nodes.openModal.addEventListener("click", openModal);
        nodes.modalClose.addEventListener("click", closeModal);
        nodes.modalCancel.addEventListener("click", closeModal);
        nodes.modalBackdrop.addEventListener("click", closeModal);
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && !nodes.modal.hidden) {
                closeModal();
            }
        });
    }

    function bindForm() {
        nodes.form.addEventListener("submit", async (event) => {
            event.preventDefault();
            clearErrors();

            const payload = {
                name: nodes.name.value.trim(),
                host: nodes.host.value.trim(),
                port: Number(nodes.port.value),
            };

            setStatus("Saving server...");
            try {
                await invoke("save_server", { payload });
                nodes.form.reset();
                nodes.port.value = "5050";
                closeModal();
                await loadServers("Server saved.");
            } catch (error) {
                showModalError(String(error));
            } finally {
                clearStatus();
            }
        });
    }

    function bindListActions() {
        nodes.list.addEventListener("click", async (event) => {
            const connectButton = event.target.closest("[data-connect-server-id]");
            if (connectButton) {
                const serverId = connectButton.dataset.connectServerId;
                state.busyServerId = serverId;
                renderServers();
                clearErrors();
                setStatus("Opening server workspace...");
                try {
                    const result = await invoke("connect_to_server", { serverId });
                    setStatus(`Connected to ${result.name}.`);
                } catch (error) {
                    showPageError(String(error));
                    clearStatus();
                } finally {
                    state.busyServerId = "";
                    renderServers();
                }
                return;
            }

            const deleteButton = event.target.closest("[data-delete-server-id]");
            if (deleteButton) {
                const serverId = deleteButton.dataset.deleteServerId;
                clearErrors();
                setStatus("Deleting server...");
                try {
                    await invoke("delete_server", { serverId });
                    await loadServers("Server deleted.");
                } catch (error) {
                    showPageError(String(error));
                } finally {
                    clearStatus();
                }
            }
        });
    }

    function bindExternalLinks() {
        document.addEventListener("click", async (event) => {
            const link = event.target.closest("[data-external-url]");
            if (!link) {
                return;
            }

            event.preventDefault();
            const url = String(link.dataset.externalUrl || "").trim();
            if (!url) {
                return;
            }

            clearErrors();
            setStatus("Opening link in your browser...");
            try {
                if (typeof invoke === "function") {
                    await invoke("open_external_url", { url });
                } else {
                    window.open(url, "_blank", "noopener,noreferrer");
                }
                setStatus("Browser opened.");
            } catch (error) {
                showPageError(String(error));
                clearStatus();
            }
        });
    }

    async function loadServers(statusMessage = "") {
        clearErrors();
        if (statusMessage) {
            setStatus(statusMessage);
        }
        try {
            state.servers = await invoke("list_servers");
            renderServers();
        } catch (error) {
            showPageError(String(error));
        }
    }

    async function loadTheme() {
        try {
            const theme = normalizeTheme(await invoke("get_client_theme"));
            applyTheme(theme);
        } catch (_error) {
            applyTheme("light");
        }
    }

    function renderServers() {
        if (!state.servers.length) {
            nodes.list.innerHTML = `
                <div class="server-empty">
                    No servers have been registered yet. Add a server to open Zertan in the desktop client.
                </div>
            `;
            return;
        }

        nodes.list.innerHTML = state.servers.map((server) => renderServer(server)).join("");
    }

    function renderServer(server) {
        const addedOn = server.added_at
            ? new Date(server.added_at).toLocaleString()
            : "Unknown date";
        const isBusy = state.busyServerId === server.id;
        return `
            <article class="server-card">
                <div>
                    <h3>${escapeHtml(server.name)}</h3>
                    <p class="muted">${escapeHtml(server.host)}:${escapeHtml(String(server.port))}</p>
                    <div class="server-meta">
                        <span class="server-chip">Added · ${escapeHtml(addedOn)}</span>
                    </div>
                </div>
                <div class="server-card__actions">
                    <button class="button button--secondary" type="button" data-delete-server-id="${escapeHtml(server.id)}">Delete</button>
                    <button class="button button--primary" type="button" data-connect-server-id="${escapeHtml(server.id)}" ${isBusy ? "disabled" : ""}>
                        ${isBusy ? "Connecting..." : "Connect"}
                    </button>
                </div>
            </article>
        `;
    }

    function openModal() {
        nodes.modal.hidden = false;
        document.body.classList.add("modal-open");
        nodes.name.focus({ preventScroll: true });
    }

    function closeModal() {
        nodes.modal.hidden = true;
        document.body.classList.remove("modal-open");
        nodes.modalError.hidden = true;
        nodes.modalError.textContent = "";
    }

    function showModalError(message) {
        nodes.modalError.textContent = message;
        nodes.modalError.hidden = false;
    }

    function showPageError(message) {
        nodes.pageError.textContent = message;
        nodes.pageError.hidden = false;
    }

    function clearErrors() {
        nodes.pageError.hidden = true;
        nodes.pageError.textContent = "";
        nodes.modalError.hidden = true;
        nodes.modalError.textContent = "";
    }

    function setStatus(message) {
        nodes.status.textContent = message;
    }

    function clearStatus() {
        nodes.status.textContent = "";
    }

    function normalizeTheme(theme) {
        return THEMES.has(theme) ? theme : "light";
    }

    function applyTheme(theme) {
        state.theme = normalizeTheme(theme);
        document.documentElement.dataset.theme = state.theme;
        if (nodes.themeSelect) {
            nodes.themeSelect.value = state.theme;
        }
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#39;");
    }
})();
