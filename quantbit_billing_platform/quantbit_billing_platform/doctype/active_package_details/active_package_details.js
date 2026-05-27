// Copyright (c) 2026, Quantbit Technologies Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on('Active Package Details', {

    refresh: function(frm) {
        toggle_token_fields(frm);
    },

    billing_package: function(frm) {
        toggle_token_fields(frm);
    }
});


function toggle_token_fields(frm) {

    if (!frm.doc.billing_package) return;

    frappe.db.get_value(
        "Billing Package",
        frm.doc.billing_package,
        "package_type"
    ).then(r => {

        if (!r.message) return;

        let type = r.message.package_type;

        if (type === "Token Based") {
            frm.set_df_property("total_tokens", "hidden", 0);
            frm.set_df_property("remaining_tokens", "hidden", 0);
        } else {
            frm.set_df_property("total_tokens", "hidden", 1);
            frm.set_df_property("remaining_tokens", "hidden", 1);
        }
    });
}