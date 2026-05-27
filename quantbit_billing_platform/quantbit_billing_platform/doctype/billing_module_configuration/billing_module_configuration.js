// Copyright (c) 2026, Quantbit Technologies Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Billing Module Configuration", {
    setup: function(frm) {
        frm.set_query("feature_list", "app_feature_details", function(doc, cdt, cdn) {
            return {
                filters: {
                    "app": doc.app
                }
            };
        });
    },
    onload: function (frm) {
        frm._previous_app = frm.doc.app;
    },
    refresh: function (frm) {
        load_apps(frm);
    },
    app: function (frm) {
        if (!frm.doc.app) { 
            frm.clear_table("billing_module_list");
            frm.refresh_field("billing_module_list");
            frm._previous_app = null;
            return;
        }
        if (frm._previous_app !== frm.doc.app) {
            frm.clear_table("billing_module_list");
            frm.refresh_field("billing_module_list");
            load_modules(frm);
        }
        frm._previous_app = frm.doc.app;
    }
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
            if (frm.fields_dict.billing_details) {
                frm.fields_dict.billing_details.grid.update_docfield_property(
                    "app_name",
                    "options",
                    options
                );
                frm.refresh_field("billing_details");
            }
        }
    });
}

function load_modules(frm) {
    frappe.call({
        method: "quantbit_billing_platform.quantbit_billing_platform.doctype.billing_module_configuration.billing_module_configuration.get_modules_from_app",
        args: {
            app_name: frm.doc.app
        },
        callback: function (r) {
            if (!r.message || !r.message.length) return;
            r.message.forEach(function (module) {
                let row = frm.add_child("billing_module_list");
                row.module_name = module.name;
                row.enabled = 0;
            });
            frm.refresh_field("billing_module_list");
        }
    });
}