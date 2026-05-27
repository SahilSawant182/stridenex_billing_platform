// Copyright (c) 2026, Quantbit Technologies Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Billing Coupon Code", {

    coupon_name(frm) {

        if (!frm.doc.coupon_name) return;

        let code = frm.doc.coupon_name
            .replace(/\s+/g, "")
            .toUpperCase()
            .slice(0, 8);

        frm.set_value("coupon_code", code);
    }

});