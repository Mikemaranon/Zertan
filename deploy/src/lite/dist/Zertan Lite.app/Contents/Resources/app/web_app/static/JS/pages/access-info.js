import { escapeHtml, request } from "../core/api.js";

export async function initAccessInfoPage() {
    const state = {
        payload: null,
    };

    const nodes = {
        primary: document.getElementById("access-primary-endpoint"),
        runtime: document.getElementById("access-runtime-summary"),
        aliases: document.getElementById("access-shared-aliases"),
        toolbar: document.getElementById("access-alias-toolbar"),
        openModalButton: document.getElementById("open-access-alias-modal"),
        form: document.getElementById("access-alias-form"),
        error: document.getElementById("access-alias-error"),
    };
    const aliasModal = bindManagedModal({
        modalId: "access-alias-modal",
        backdropId: "access-alias-modal-backdrop",
        closeButtonId: "access-alias-modal-close",
        cancelButtonId: "access-alias-cancel",
        onClose: () => resetAliasForm(nodes),
    });

    if (!nodes.primary || !nodes.runtime || !nodes.aliases) {
        return;
    }

    nodes.openModalButton?.addEventListener("click", (event) => {
        resetAliasForm(nodes);
        aliasModal.open(event.currentTarget);
    });

    if (nodes.form) {
        nodes.form.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (nodes.error) {
                nodes.error.textContent = "";
            }

            try {
                await request("/api/system/connection-info/aliases", {
                    method: "POST",
                    body: {
                        label: document.getElementById("access-alias-label").value.trim(),
                        host: document.getElementById("access-alias-host").value.trim(),
                        port: document.getElementById("access-alias-port").value.trim(),
                    },
                });
                resetAliasForm(nodes);
                aliasModal.close();
                await loadConnectionInfo(state, nodes);
            } catch (error) {
                if (nodes.error) {
                    nodes.error.textContent = error.message;
                }
            }
        });
    }

    nodes.aliases.addEventListener("click", async (event) => {
        const button = event.target.closest("[data-delete-alias-id]");
        if (!button) {
            return;
        }
        try {
            await request(`/api/system/connection-info/aliases/${button.dataset.deleteAliasId}`, {
                method: "DELETE",
            });
            await loadConnectionInfo(state, nodes);
        } catch (error) {
            if (nodes.error) {
                nodes.error.textContent = error.message;
            }
        }
    });

    await loadConnectionInfo(state, nodes);
}

async function loadConnectionInfo(state, nodes) {
    const payload = await request("/api/system/connection-info");
    state.payload = payload;
    syncAliasManagementVisibility(nodes, Boolean(payload.can_manage_aliases));
    renderPrimary(nodes.primary, payload.primary_endpoint);
    renderRuntime(nodes.runtime, payload.connection);
    renderAliases(nodes.aliases, payload.aliases || [], Boolean(payload.can_manage_aliases));
}

function renderPrimary(node, endpoint) {
    if (!endpoint) {
        node.innerHTML = `<div class="empty-state">Connection details are not available yet.</div>`;
        return;
    }

    node.innerHTML = `
        <article class="access-card">
            <div class="access-card__top">
                <div>
                    <h3>${escapeHtml(endpoint.label)}</h3>
                    <div class="access-card__endpoint">
                        <span class="access-inline-code">${escapeHtml(endpoint.host || "Unavailable")}</span>
                        <span>|</span>
                        <span class="access-inline-code">PORT ${escapeHtml(String(endpoint.port || ""))}</span>
                    </div>
                </div>
                <span class="badge ${statusClassName(endpoint.verification_status)}">${escapeHtml(statusLabel(endpoint.verification_status))}</span>
            </div>
            <p>${escapeHtml(endpoint.verification_message || "")}</p>
            ${endpoint.url ? `<div class="access-card__meta"><span>URL</span><strong class="access-inline-code">${escapeHtml(endpoint.url)}</strong></div>` : ""}
        </article>
    `;
}

function renderRuntime(node, connection) {
    const detected = (connection.detected_ipv4_addresses || []).length
        ? connection.detected_ipv4_addresses.map((item) => `<span class="badge">${escapeHtml(item)}</span>`).join("")
        : `<span class="muted">No extra IPv4 interfaces were detected.</span>`;

    node.innerHTML = `
        <article class="access-runtime-item">
            <h3>Listening address</h3>
            <p><strong class="access-inline-code">${escapeHtml(connection.listen_host)}:${escapeHtml(String(connection.listen_port))}</strong></p>
            <p class="muted">${escapeHtml(connection.share_hint || "")}</p>
        </article>
        <article class="access-runtime-item">
            <h3>Detected network addresses</h3>
            <div class="badge-row">${detected}</div>
        </article>
    `;
}

function renderAliases(node, aliases, canManageAliases) {
    if (!aliases.length) {
        node.innerHTML = `<div class="empty-state">No shared aliases have been published yet.</div>`;
        return;
    }

    node.innerHTML = `<div class="access-alias-list">${aliases.map((alias) => renderAlias(alias, canManageAliases)).join("")}</div>`;
}

function renderAlias(alias, canManageAliases) {
    const hostGroup = alias.host_type === "dns" ? "dns" : "ip";
    return `
        <article class="access-alias-card">
            <div class="access-alias-card__top">
                <div>
                    <h3>${escapeHtml(alias.label || alias.host)}</h3>
                    <div class="access-alias-card__endpoint">
                        <span class="selection-chip selection-chip--static" data-group="${escapeHtml(hostGroup)}">
                            <span class="selection-chip__group">${escapeHtml(hostGroup.toUpperCase())}</span>
                            <span class="selection-chip__value access-inline-code">${escapeHtml(alias.host)}</span>
                        </span>
                        <span class="selection-chip selection-chip--static" data-group="port">
                            <span class="selection-chip__group">PORT</span>
                            <span class="selection-chip__value access-inline-code">${escapeHtml(String(alias.effective_port))}</span>
                        </span>
                    </div>
                </div>
                <span class="badge ${statusClassName(alias.verification_status)}">${escapeHtml(statusLabel(alias.verification_status))}</span>
            </div>
            <p>${escapeHtml(alias.verification_message || "")}</p>
            <div class="access-alias-card__meta">
                <span class="access-alias-card__timestamp">Last check: <strong>${escapeHtml(alias.last_verified_at || "not verified yet")}</strong></span>
                ${canManageAliases ? `<button class="button button--danger button--small" type="button" data-delete-alias-id="${escapeHtml(String(alias.id))}">Delete</button>` : ""}
            </div>
        </article>
    `;
}

function statusLabel(status) {
    if (status === "verified") {
        return "Verified";
    }
    if (status === "mismatch") {
        return "Mismatch";
    }
    if (status === "unreachable") {
        return "Unreachable";
    }
    if (status === "error") {
        return "Error";
    }
    return "Pending";
}

function statusClassName(status) {
    if (status === "verified") {
        return "badge--active";
    }
    return "badge--pending";
}

function syncAliasManagementVisibility(nodes, canManageAliases) {
    if (nodes.toolbar) {
        nodes.toolbar.hidden = !canManageAliases;
    }
    if (!canManageAliases) {
        resetAliasForm(nodes);
    }
}

function resetAliasForm(nodes) {
    if (nodes.form) {
        nodes.form.reset();
    }
    if (nodes.error) {
        nodes.error.textContent = "";
    }
}

function bindManagedModal({ modalId, backdropId, closeButtonId, cancelButtonId, onClose }) {
    const modal = document.getElementById(modalId);
    const backdrop = document.getElementById(backdropId);
    const closeButton = document.getElementById(closeButtonId);
    const cancelButton = cancelButtonId ? document.getElementById(cancelButtonId) : null;
    if (!modal || !backdrop || !closeButton) {
        return { open() {}, close() {} };
    }

    let isClosing = false;
    let lastTrigger = null;

    function open(trigger = null) {
        if (!modal.hidden && modal.dataset.state === "open") {
            return;
        }
        lastTrigger = trigger instanceof HTMLElement ? trigger : document.activeElement;
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

    function close() {
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
            if (typeof onClose === "function") {
                onClose();
            }
            if (lastTrigger instanceof HTMLElement && lastTrigger.isConnected) {
                lastTrigger.focus({ preventScroll: true });
            }
        }, 300);
    }

    closeButton.addEventListener("click", close);
    backdrop.addEventListener("click", close);
    cancelButton?.addEventListener("click", close);

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !modal.hidden) {
            close();
        }
    });

    return { open, close };
}
