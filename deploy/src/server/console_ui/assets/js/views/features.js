(function (App) {
    App.buildFeaturesView = function () {
        const data = App.snapshot();
        const stack = App.createNode("div", "content-stack content-stack--two-rows");
        const hero = App.createNode("section", "panel hero-panel");
        const heroText = document.createElement("div");
        heroText.append(
            App.createNode("p", "eyebrow", "Features"),
            App.createNode("h2", "", "Operational feature toggles"),
            App.createNode("p", "", "Flip site capabilities from the embedded server console without opening the browser admin page first.")
        );
        const heroMeta = App.createNode("div", "hero-meta");
        heroMeta.append(
            App.badgeNode("badge badge--primary", `${(data.features || []).length} registered`),
            App.badgeNode("badge badge--ok", `${data.stats && data.stats.enabled_features ? data.stats.enabled_features : 0} enabled`)
        );
        hero.append(heroText, heroMeta);

        const panel = App.createNode("section", "panel panel--fill");
        panel.append(App.panelHeading("Feature flags", "Live configuration", "Changes are persisted immediately to the current domain database."));
        const list = App.createNode("div", "feature-list panel-scroll");
        list.dataset.scrollKey = "features-list";
        if (!(data.features || []).length) {
            list.append(App.createNode("div", "empty-state", "No site features are registered."));
        } else {
            (data.features || []).forEach((feature) => {
                const row = App.createNode("label", "feature-toggle-row");
                const copy = App.createNode("div", "feature-toggle-row__copy");
                copy.append(
                    App.createNode("strong", "", feature.label),
                    App.createNode("p", "", feature.description || feature.feature_key)
                );
                const toggle = App.createNode("span", "feature-toggle");
                const input = document.createElement("input");
                input.type = "checkbox";
                input.checked = !!feature.enabled;
                input.disabled = !!App.state.featureBusy[feature.feature_key];
                input.addEventListener("change", () => App.toggleFeature(feature.feature_key, input.checked));
                const track = App.createNode("span", "feature-toggle__track");
                toggle.append(input, track);
                row.append(copy, toggle);
                list.append(row);
            });
        }
        panel.append(list);
        stack.append(hero, panel);
        return stack;
    };
})(window.ServerConsole);
