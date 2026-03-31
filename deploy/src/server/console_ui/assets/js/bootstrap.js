(function (App) {
    window.addEventListener("pywebviewready", async () => {
        const bridge = App.api();
        if (bridge && typeof bridge.get_console_snapshot === "function") {
            try {
                App.state.snapshot = await bridge.get_console_snapshot();
            } catch (error) {
                console.error("Unable to load initial bridge state", error);
            }
        }
        App.initialize();
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => {
            if (!App.api()) {
                App.initialize();
            }
        });
    } else if (!App.api()) {
        App.initialize();
    }
})(window.ServerConsole);
