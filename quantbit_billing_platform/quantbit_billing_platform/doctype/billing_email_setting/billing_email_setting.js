// Copyright (c) 2026, Quantbit Technologies Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Billing Email Setting", {
    setup(frm) {
        frm.set_query("doctype_name", function () {
            return {
                query: "quantbit_billing_platform.quantbit_billing_platform.doctype.billing_email_setting.billing_email_setting.get_allowed_doctypes"
            };
        });
    },

    doctype_name(frm) {

        if (!frm.doc.doctype_name) return;

        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "DocType",
                name: frm.doc.doctype_name
            },
            callback: function (r) {

                if (!r.message) return;

                let options = [];

                (r.message.fields || []).forEach(field => {

                    if (
                        field.fieldname &&
                        ![
                            "Section Break",
                            "Column Break",
                            "HTML",
                            "Table"
                        ].includes(field.fieldtype)
                    ) {
                        options.push(field.fieldname);   // ✅ only fieldname
                    }

                });

                let option_string = options.join("\n");

                // ✅ Update parent select field
                frm.set_df_property(
                    "field_name",
                    "options",
                    option_string
                );

                frm.refresh_field("field_name");


                // ✅ Update child table select field
                frm.fields_dict.template_values.grid.update_docfield_property(
                    "select_field",
                    "options",
                    option_string
                );

                frm.fields_dict.template_values.grid.refresh();

            }
        });

    }
});
