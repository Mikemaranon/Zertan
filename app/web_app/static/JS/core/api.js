export async function request(endpoint, { method = "GET", body = null, formData = null } = {}) {
    const headers = {};

    const options = {
        method,
        headers,
        credentials: "same-origin",
    };

    if (formData) {
        options.body = formData;
    } else if (body !== null) {
        headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(body);
    }

    const response = await fetch(endpoint, options);
    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json") ? await response.json() : await response.text();

    if (!response.ok) {
        if (response.status === 401 && document.body.dataset.page !== "login") {
            window.location.href = "/login";
        }
        const message = typeof payload === "string" ? payload : payload.error || "Request failed.";
        throw new Error(message);
    }

    return payload;
}

export function getCurrentUser() {
    return parseEmbeddedJson("current-user-data");
}

export function getPageContext() {
    return parseEmbeddedJson("page-context-data");
}

export function parseEmbeddedJson(id) {
    const node = document.getElementById(id);
    if (!node) {
        return {};
    }
    try {
        return JSON.parse(node.textContent);
    } catch (error) {
        return {};
    }
}

export function assetPathToUrl(path) {
    if (!path) {
        return "";
    }
    if (path.startsWith("/")) {
        return path;
    }
    if (path.startsWith("web_app/")) {
        return `/${path.replace(/^web_app\//, "")}`;
    }
    return `/media/${path.replace(/^web_server\/data_m\/assets\//, "").replace(/^\/+/, "")}`;
}

export function splitCommaValues(value) {
    return value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
}

export function formatPercent(value) {
    return `${Number(value || 0).toFixed(1)}%`;
}

export function formatDuration(seconds) {
    const total = Number(seconds || 0);
    if (!total) {
        return "n/a";
    }
    const minutes = Math.floor(total / 60);
    const remaining = total % 60;
    if (minutes < 60) {
        return `${minutes}m ${remaining}s`;
    }
    const hours = Math.floor(minutes / 60);
    return `${hours}h ${minutes % 60}m`;
}

export function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}
