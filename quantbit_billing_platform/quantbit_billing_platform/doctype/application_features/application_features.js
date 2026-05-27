// Copyright (c) 2026, Quantbit Technologies Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Application Features", {
	refresh(frm) {
		load_apps(frm);
	},
});

function load_apps(frm) {
    frappe.call({
        method: "frappe.core.doctype.module_def.module_def.get_installed_apps",
        callback: function (r) {
            if (!r.message) return;

            let apps = JSON.parse(r.message);
            apps = apps.filter(app => !["frappe", "erpnext", "quantbit_billing_platform", "india_compliance", "uichange","quantbit_dark_theme","erp_ui"].includes(app));
            let options = apps.join("\n");

            if (frm.fields_dict.app) {
                frm.set_df_property("app", "options", options);
            }
        }
    });
}
