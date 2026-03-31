(function (App) {
    App.createNode = function (tag, className, text) {
        const node = document.createElement(tag);
        if (className) {
            node.className = className;
        }
        if (text !== undefined) {
            node.textContent = text;
        }
        return node;
    };

    App.badgeNode = function (className, text) {
        return App.createNode("span", className, text);
    };

    App.buildBadgeForStatus = function (status) {
        const value = String(status || "").toLowerCase();
        if (value === "verified" || value === "healthy" || value === "active" || value === "enabled" || value === "success") {
            return "badge badge--ok";
        }
        if (value === "mismatch" || value === "warning" || value === "redirect") {
            return "badge badge--warning";
        }
        if (
            value === "disabled" ||
            value === "inactive" ||
            value === "error" ||
            value === "unreachable" ||
            value === "client_error" ||
            value === "server_error"
        ) {
            return "badge badge--danger";
        }
        return "badge badge--primary";
    };

    App.panelHeading = function (label, title, subtitle) {
        const heading = App.createNode("div", "panel-heading");
        const left = document.createElement("div");
        left.append(
            App.createNode("div", "panel-label", label),
            App.createNode("h3", "", title),
            App.createNode("p", "", subtitle)
        );
        heading.append(left);
        return heading;
    };

    App.actionButton = function (label, className, onClick, disabled) {
        const button = App.createNode("button", className, label);
        button.type = "button";
        button.disabled = !!disabled;
        button.addEventListener("click", onClick);
        return button;
    };

    App.buildDetailSection = function (title, items) {
        return {
            title,
            type: "grid",
            items
        };
    };

    App.buildCodeSection = function (title, value) {
        const rendered = value && typeof value === "object" ? JSON.stringify(value, null, 2) : String(value || "");
        return {
            title,
            type: "code",
            value: rendered || "No data available."
        };
    };

    App.initialsFromText = function (value) {
        const cleaned = String(value || "").trim();
        if (!cleaned) {
            return "ZT";
        }
        const parts = cleaned.split(/\s+/).filter(Boolean).slice(0, 2);
        if (!parts.length) {
            return cleaned.slice(0, 2).toUpperCase();
        }
        return parts.map((part) => part[0]).join("").slice(0, 2).toUpperCase();
    };
})(window.ServerConsole);
