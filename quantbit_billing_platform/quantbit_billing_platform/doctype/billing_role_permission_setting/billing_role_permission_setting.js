// Copyright (c) 2026, Quantbit Technologies Pvt Ltd and contributors
// For license information, please see license.txt


frappe.ui.form.on('Billing Role Permission Setting', {

    select_doctype: function(frm) {

        // Must select Billing Role first
        if (!frm.doc.billing_role) {
            frappe.msgprint(__('Please select a Billing Role first.'));
            return;
        }

        // Get Module from Billing Role
        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "Billing Role",
                name: frm.doc.billing_role
            },
            callback: function(res) {

                if (!res.message) {
                    frappe.msgprint(__('Unable to fetch Billing Role.'));
                    return;
                }

                let module_name = res.message.module;

                if (!module_name) {
                    frappe.msgprint(__('No Module linked in Billing Role.'));
                    return;
                }

                // Now fetch doctypes of that module
                frappe.call({
                    method: "frappe.client.get_list",
                    args: {
                        doctype: "DocType",
                        fields: ["name"],
                        filters: {
                            module: module_name,
                            istable: 0
                        },
                        limit_page_length: 1000
                    },
                    callback: function(r) {

                        if (!r.message || r.message.length === 0) {
                            frappe.msgprint(__('No Doctypes found.'));
                            return;
                        }

                        let all_doctypes = r.message.map(d => d.name);

                        let dialog = new frappe.ui.Dialog({
                            title: __('Select Doctypes'),
                            size: 'large',
                            fields: [
                                {
                                    fieldtype: 'Data',
                                    fieldname: 'search',
                                    label: __('Search')
                                },
                                {
                                    fieldtype: 'HTML',
                                    fieldname: 'doctype_list'
                                }
                            ],
                            primary_action_label: __('Add Doctypes'),
                            primary_action() {

                                let selected = [];

                                dialog.$wrapper.find('.doctype-check:checked').each(function() {
                                    selected.push($(this).val());
                                });

                                if (!selected.length) {
                                    frappe.msgprint(__('Select at least one Doctype.'));
                                    return;
                                }

                                selected.forEach(dt => { 

                                    let exists = (frm.doc.doctypes || []).some(row =>
                                        row.doctype_name === dt
                                    );

                                    if (!exists) {
                                        let row = frm.add_child('doctypes');
                                        row.doctype_name = dt;
                                    }
                                });

                                frm.refresh_field('doctypes');
                                dialog.hide();
                            }
                        });

                        function render(filter="") {

                            let filtered = all_doctypes
                                .filter(d => d.toLowerCase().includes(filter.toLowerCase()));

                            let html = `
                                <div style="padding:8px 0;">
                                    <button class="btn btn-sm btn-primary select-all-btn">Select All</button>
                                    <button class="btn btn-sm btn-secondary unselect-all-btn" style="margin-left:8px;">Unselect All</button>
                                </div>

                                <div style="max-height:400px; overflow:auto;">
                            `;

                            filtered.forEach(d => {
                                html += `
                                    <div style="padding:4px 0;">
                                        <input type="checkbox"
                                            class="doctype-check"
                                            value="${d}">
                                        ${d}
                                    </div>
                                `;
                            });

                            html += `</div>`;

                            dialog.fields_dict.doctype_list.$wrapper.html(html);

                            dialog.$wrapper.find('.select-all-btn').on('click', function() {
                                dialog.$wrapper.find('.doctype-check').prop('checked', true);
                            });

                            dialog.$wrapper.find('.unselect-all-btn').on('click', function() {
                                dialog.$wrapper.find('.doctype-check').prop('checked', false);
                            });
                        }



                        

                        dialog.fields_dict.search.$input.on('input', function() {
                            render(this.value);
                        });

                        render();
                        dialog.show();
                    }
                });

            }
        });
    }
});
