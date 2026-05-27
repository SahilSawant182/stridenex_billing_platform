// Copyright (c) 2026, Quantbit Technologies Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on('Billing Account Master', {


    refresh(frm) {
        
        set_role_filter(frm);

        if (frm.doc.billing_user_detail) {
            $.each(frm.doc.billing_user_detail, function(i, row) {
                load_roles_for_row(frm, row.doctype, row.name);
            });
        }

        if (!frm.doc.is_master_user) {
            frm.set_df_property('billing_user_detail', 'hidden', 1);
        } else {
            frm.set_df_property('billing_user_detail', 'hidden', 0);
        }

        frm.set_df_property('user_password', 'fieldtype', 'Password');

        const master_input = frm.get_field('user_password').$input;
        if (master_input) {
            master_input.attr('type', 'password');
        }

        if (frm.fields_dict.billing_user_detail) {
            frm.fields_dict.billing_user_detail.grid.update_docfield_property(
                'user_password',
                'fieldtype',
                'Password'
            );

            frm.fields_dict.billing_user_detail.grid.wrapper.on(
                'focus',
                'input[data-fieldname="user_password"]',
                function () {
                    $(this).attr('type', 'password');
                }
            );
        }

        set_full_name(frm);
    },

    billing_details(frm) {
        if (frm.doc.billing_user_detail) {
            $.each(frm.doc.billing_user_detail, function(i, row) {
                load_roles_for_row(frm, row.doctype, row.name);
            });
        }
    },

    first_name(frm) { set_full_name(frm); },
    middle_name(frm) { set_full_name(frm); },
    last_name(frm) { set_full_name(frm); }

});

frappe.ui.form.on("Billing User Detail", {
    app_name: function(frm, cdt, cdn) {
        frappe.model.set_value(cdt, cdn, "user_role", "");
        load_roles_for_row(frm, cdt, cdn);
    }
});

function load_roles_for_row(frm, cdt, cdn) {
    let row = locals[cdt][cdn];

    if (!row.app_name) {
        row.__allowed_roles = [];
        return;
    }

    let billing_row = (frm.doc.billing_details || []).find(d => d.app_name === row.app_name);

    if (!billing_row || !billing_row.billing_role) {
        row.__allowed_roles = [];
        return;
    }

    frappe.call({
        method: "frappe.client.get",
        args: {
            doctype: "Billing Role",
            name: billing_row.billing_role
        },
        callback: function (r) {
            let roles = [];
            if (r.message && r.message.billing_role_list) {
                r.message.billing_role_list.forEach(role_row => {
                    if (role_row.billing_role && !roles.includes(role_row.billing_role)) {
                        roles.push(role_row.billing_role);
                    }
                });
            }
            row.__allowed_roles = roles;
        }
    });
}

function set_role_filter(frm) {
    frm.fields_dict.billing_user_detail.grid.get_field("user_role").get_query = function (doc, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (!row.__allowed_roles || row.__allowed_roles.length === 0) {
            return { filters: { name: ["in", [""]] } };
        }

        return {
            filters: {
                name: ["in", row.__allowed_roles]
            }
        };
    };
}


function set_full_name(frm) {
    let first = frm.doc.first_name || "";
    let middle = frm.doc.middle_name || "";
    let last = frm.doc.last_name || "";
    let full_name = "";

    if (first) full_name += first;
    if (middle) full_name += (full_name ? " " : "") + middle;
    if (last) full_name += (full_name ? " " : "") + last;

    frm.set_value("full_name", full_name.trim());
}

frappe.ui.form.on("Billing Details", {
    billing_package: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.billing_package) return;
        set_package_id(frm);
    }
});

function set_package_id(frm) {
    let unique_id = "PKG-" + frappe.datetime.now_datetime();
    frm.set_value("package_id", unique_id);
}