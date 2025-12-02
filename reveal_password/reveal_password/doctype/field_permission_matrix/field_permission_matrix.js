// Copyright (c) 2025, Abhishek Chougule and contributors
// For license information, please see license.txt

frappe.ui.form.on('Field Permission Matrix', {
    refresh: function (frm) {
        // Add custom buttons
        if (!frm.is_new()) {
            frm.add_custom_button(__('Test Permission'), function () {
                test_permission(frm);
            });
        }

        // Set field descriptions
        frm.set_df_property('role', 'description',
            'Select the role that will have permission to reveal this field');
        frm.set_df_property('doctype_name', 'description',
            'Select the DocType containing the password field');
        frm.set_df_property('field_name', 'description',
            'Enter the exact field name (case-sensitive)');
    },

    doctype_name: function (frm) {
        if (frm.doc.doctype_name) {
            // Fetch and suggest password fields from the selected DocType
            frappe.call({
                method: 'reveal_password.reveal_password.doctype.field_permission_matrix.field_permission_matrix.get_password_fields',
                args: {
                    doctype: frm.doc.doctype_name
                },
                callback: function (r) {
                    if (r.message && r.message.length > 0) {
                        frm.set_df_property('field_name', 'options', r.message.join('\n'));
                        frm.set_df_property('field_name', 'fieldtype', 'Select');

                        frappe.show_alert({
                            message: __('Found {0} password field(s)', [r.message.length]),
                            indicator: 'green'
                        }, 3);
                    } else {
                        frm.set_df_property('field_name', 'fieldtype', 'Data');
                        frappe.show_alert({
                            message: __('No password fields found in this DocType'),
                            indicator: 'orange'
                        }, 3);
                    }
                }
            });
        }
    },

    can_reveal: function (frm) {
        if (frm.doc.can_reveal) {
            frappe.show_alert({
                message: __('Permission granted for {0}', [frm.doc.role || 'this role']),
                indicator: 'green'
            }, 2);
        }
    }
});

function test_permission(frm) {
    frappe.prompt([
        {
            fieldname: 'user',
            label: __('User'),
            fieldtype: 'Link',
            options: 'User',
            reqd: 1,
            description: __('Select a user to test permissions for')
        }
    ], function (values) {
        frappe.call({
            method: 'reveal_password.reveal.has_field_permission',
            args: {
                doctype: frm.doc.doctype_name,
                fieldname: frm.doc.field_name,
                user: values.user
            },
            callback: function (r) {
                if (r.message) {
                    frappe.msgprint({
                        title: __('Permission Test Result'),
                        message: __('User <b>{0}</b> <span class="text-success">CAN</span> reveal field <b>{1}</b> in <b>{2}</b>',
                            [values.user, frm.doc.field_name, frm.doc.doctype_name]),
                        indicator: 'green'
                    });
                } else {
                    frappe.msgprint({
                        title: __('Permission Test Result'),
                        message: __('User <b>{0}</b> <span class="text-danger">CANNOT</span> reveal field <b>{1}</b> in <b>{2}</b>',
                            [values.user, frm.doc.field_name, frm.doc.doctype_name]),
                        indicator: 'red'
                    });
                }
            }
        });
    }, __('Test Permission'), __('Test'));
}
