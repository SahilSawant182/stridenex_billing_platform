// Copyright (c) 2026, Quantbit Technologies Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Billing Package", {



    refresh: function (frm) {
        toggle_fields(frm);


        if (frm.doc.is_user_package) {
            frm.set_value("billing_role", "User Role");
            frm.set_df_property("billing_role", "read_only", 1);
        } else {
            frm.set_df_property("billing_role", "read_only", 0);
        }
    },

    // is_user_package: function(frm) {

    //     if (frm.doc.is_user_package) {
    //         frm.set_value("billing_role", "User Role");

    //         frm.set_df_property("billing_role", "read_only", 1);

    //     } else {

    //         frm.set_df_property("billing_role", "read_only", 0);
    //     }
    // },

    package_type: function (frm) {
        toggle_fields(frm);

        if (frm.doc.package_type === "Token Based" && frm.doc.billing_role) {
            load_doctypes(frm);
        }
    },

    billing_role: function (frm) {
        if (frm.doc.package_type === "Token Based" && frm.doc.billing_role) {
            load_doctypes(frm);
        }
    },

    app_name: function (frm) {

        // if (!frm.doc.app_name || !frm.app_map) return;
        // let actual_app = frm.app_map[frm.doc.app_name];

        // if (actual_app) {
        //     frm.set_value("app", actual_app);  
        // }
        frm.set_value("app", frm.doc.app_name);
    }
});

// Toggle fields based on package type
function toggle_fields(frm) {

    if (frm.doc.package_type === "Token Based") {

        frm.set_df_property("billing_package_token_detail", "hidden", 0);
        frm.set_df_property("no_of_days", "hidden", 1);

    }

    else if (frm.doc.package_type === "Day Based") {

        frm.set_df_property("billing_package_token_detail", "hidden", 1);
        frm.set_df_property("no_of_days", "hidden", 0);

        if (frm.doc.billing_package_token_detail &&
            frm.doc.billing_package_token_detail.length > 0) {

            frm.clear_table("billing_package_token_detail");
            frm.refresh_field("billing_package_token_detail");
        }
    }

    else {

        frm.set_df_property("billing_package_token_detail", "hidden", 1);
        frm.set_df_property("no_of_days", "hidden", 1);

    }
}


// Load doctypes based on billing role
function load_doctypes(frm) {

    if (frm.doc.billing_package_token_detail &&
        frm.doc.billing_package_token_detail.length > 0) {
        return;
    }

    frappe.call({
        method: "quantbit_billing_platform.quantbit_billing_platform.doctype.billing_package.billing_package.get_doctypes_from_role",

        args: {
            role: frm.doc.billing_role
        },

        callback: function (r) {

            if (r.message && Array.isArray(r.message)) {

                r.message.forEach(function (dt) {

                    let row = frm.add_child("billing_package_token_detail");
                    row.ref_doctype = dt;
                    row.token_utilization_per_request = 0;

                });

                frm.refresh_field("billing_package_token_detail");
            }

        }
    });
}