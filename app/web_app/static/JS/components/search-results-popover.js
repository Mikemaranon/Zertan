export function createSearchResultsPopover(anchorNode, panelNode, {
    minWidth = 220,
    maxHeight = 320,
    viewportPadding = 16,
    offset = 8,
    renderPanel = null,
} = {}) {
    if (!anchorNode || !panelNode) {
        return {
            close() {},
            isOpen() { return false; },
            refresh() {},
            updatePosition() {},
        };
    }

    panelNode.dataset.floatingPanel = "true";
    panelNode.hidden = true;

    function isOpen() {
        return !panelNode.hidden;
    }

    function updatePosition() {
        if (!isOpen()) {
            return;
        }

        const rect = anchorNode.getBoundingClientRect();
        const isOutsideViewport =
            rect.bottom < viewportPadding ||
            rect.top > window.innerHeight - viewportPadding ||
            rect.right < viewportPadding ||
            rect.left > window.innerWidth - viewportPadding;

        if (isOutsideViewport || rect.width <= 0 || rect.height <= 0) {
            close();
            return;
        }

        const width = Math.min(
            Math.max(rect.width, minWidth),
            Math.max(minWidth, window.innerWidth - viewportPadding * 2),
        );
        const left = Math.min(
            Math.max(viewportPadding, rect.left),
            Math.max(viewportPadding, window.innerWidth - width - viewportPadding),
        );
        const availableBelow = Math.max(120, window.innerHeight - rect.bottom - offset - viewportPadding);
        const availableAbove = Math.max(120, rect.top - offset - viewportPadding);
        const shouldOpenAbove = availableBelow < 180 && availableAbove > availableBelow;
        const nextMaxHeight = Math.min(maxHeight, shouldOpenAbove ? availableAbove : availableBelow);

        panelNode.style.left = `${left}px`;
        panelNode.style.width = `${width}px`;
        panelNode.style.maxHeight = `${nextMaxHeight}px`;

        const renderedHeight = Math.min(panelNode.scrollHeight, nextMaxHeight);
        const top = shouldOpenAbove
            ? Math.max(viewportPadding, rect.top - renderedHeight - offset)
            : Math.min(window.innerHeight - renderedHeight - viewportPadding, rect.bottom + offset);

        panelNode.style.top = `${Math.max(viewportPadding, top)}px`;
        panelNode.dataset.placement = shouldOpenAbove ? "top" : "bottom";
    }

    function open() {
        ensureFloatingPanelRoot().appendChild(panelNode);
        panelNode.hidden = false;
        updatePosition();
    }

    function close() {
        panelNode.hidden = true;
        panelNode.style.removeProperty("top");
        panelNode.style.removeProperty("left");
        panelNode.style.removeProperty("width");
        panelNode.style.removeProperty("max-height");
        delete panelNode.dataset.placement;
    }

    function refresh() {
        if (typeof renderPanel === "function") {
            renderPanel();
        }
        open();
    }

    anchorNode.addEventListener("focus", refresh);
    anchorNode.addEventListener("input", refresh);
    anchorNode.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            close();
        }
    });
    panelNode.addEventListener("pointerdown", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }
        if (target.closest("button, [role='button'], a")) {
            event.preventDefault();
        }
    });
    anchorNode.addEventListener("blur", () => {
        window.setTimeout(() => {
            const activeNode = document.activeElement;
            if (activeNode === anchorNode || panelNode.contains(activeNode)) {
                return;
            }
            close();
        }, 0);
    });

    document.addEventListener("pointerdown", (event) => {
        if (!isOpen()) {
            return;
        }
        if (anchorNode.contains(event.target) || panelNode.contains(event.target)) {
            return;
        }
        close();
    });
    document.addEventListener("scroll", () => {
        if (isOpen()) {
            updatePosition();
        }
    }, true);
    window.addEventListener("resize", () => {
        if (isOpen()) {
            updatePosition();
        }
    });

    return {
        close,
        isOpen,
        refresh,
        updatePosition,
    };
}

function ensureFloatingPanelRoot() {
    let root = document.getElementById("floating-panel-root");
    if (root) {
        return root;
    }

    root = document.createElement("div");
    root.id = "floating-panel-root";
    document.body.appendChild(root);
    return root;
}
