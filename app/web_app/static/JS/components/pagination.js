export function renderPagination(container, currentPage, totalPages, onNavigate) {
    container.innerHTML = "";
    if (totalPages <= 1) {
        return;
    }

    const wrapper = document.createElement("div");
    wrapper.className = "pagination";

    wrapper.appendChild(createPageButton("Previous", currentPage > 1, () => onNavigate(currentPage - 1)));

    for (const page of buildVisiblePages(currentPage, totalPages)) {
        if (page === "...") {
            wrapper.appendChild(createEllipsis());
            continue;
        }
        const button = createPageButton(String(page), true, () => onNavigate(page));
        button.classList.add("page-link");
        if (page === currentPage) {
            button.classList.add("active");
        }
        wrapper.appendChild(button);
    }

    wrapper.appendChild(createPageButton("Next", currentPage < totalPages, () => onNavigate(currentPage + 1)));

    const count = document.createElement("span");
    count.className = "muted";
    count.textContent = `Page ${currentPage} of ${totalPages}`;
    wrapper.appendChild(count);

    container.appendChild(wrapper);
}

function buildVisiblePages(currentPage, totalPages) {
    if (totalPages <= 4) {
        return Array.from({ length: totalPages }, (_, index) => index + 1);
    }

    if (currentPage <= 3) {
        return [...range(1, 4), "...", totalPages];
    }

    if (currentPage >= totalPages - 2) {
        return [1, "...", ...range(totalPages - 3, totalPages)];
    }

    return [1, "...", currentPage - 1, currentPage, currentPage + 1, "...", totalPages];
}

function range(start, end) {
    const values = [];
    for (let page = start; page <= end; page += 1) {
        if (page > 0) {
            values.push(page);
        }
    }
    return values;
}

function createPageButton(label, enabled, handler) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "page-link";
    button.textContent = label;
    button.disabled = !enabled;
    if (enabled) {
        button.addEventListener("click", handler);
    }
    return button;
}

function createEllipsis() {
    const node = document.createElement("span");
    node.className = "pagination-ellipsis";
    node.textContent = "...";
    return node;
}
