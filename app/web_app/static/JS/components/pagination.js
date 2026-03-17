export function renderPagination(container, currentPage, totalPages, onNavigate) {
    container.innerHTML = "";
    if (totalPages <= 1) {
        return;
    }

    const wrapper = document.createElement("div");
    wrapper.className = "pagination";

    wrapper.appendChild(createPageButton("Previous", currentPage > 1, () => onNavigate(currentPage - 1)));

    for (let page = 1; page <= totalPages; page += 1) {
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
