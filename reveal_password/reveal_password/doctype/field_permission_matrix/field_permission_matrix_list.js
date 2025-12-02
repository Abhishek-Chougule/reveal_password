// Copyright (c) 2025, Abhishek Chougule and contributors
// For license information, please see license.txt

frappe.listview_settings['Field Permission Matrix'] = {
    add_fields: ['can_reveal'],

    get_indicator: function (doc) {
        if (doc.can_reveal) {
            return [__('Allowed'), 'green', 'can_reveal,=,1'];
        } else {
            return [__('Denied'), 'red', 'can_reveal,=,0'];
        }
    },

    onload: function (listview) {
        // Add custom bulk actions
        listview.page.add_inner_button(__('Bulk Permission Manager'), function () {
            frappe.set_route('Form', 'Bulk Permission Manager', 'Bulk Permission Manager');
        });

        listview.page.add_inner_button(__('Permission Summary'), function () {
            show_permission_summary();
        });
    },

    formatters: {
        can_reveal: function (value) {
            if (value) {
                return '<span class="indicator-pill green">Allowed</span>';
            } else {
                return '<span class="indicator-pill red">Denied</span>';
            }
        }
    }
};

function show_permission_summary() {
    frappe.call({
        method: 'reveal_password.reveal_password.doctype.field_permission_matrix.field_permission_matrix.get_permission_summary',
        callback: function (r) {
            if (r.message) {
                let html = '<table class="table table-bordered">';
                html += '<thead><tr><th>DocType</th><th>Field</th><th>Role</th><th>Access</th></tr></thead>';
                html += '<tbody>';

                r.message.forEach(function (perm) {
                    let access_badge = perm.can_reveal ?
                        '<span class="badge badge-success">Allowed</span>' :
                        '<span class="badge badge-danger">Denied</span>';

                    html += `<tr>
						<td>${perm.doctype_name}</td>
						<td><code>${perm.field_name}</code></td>
						<td>${perm.role}</td>
						<td>${access_badge}</td>
					</tr>`;
                });

                html += '</tbody></table>';

                frappe.msgprint({
                    title: __('Permission Summary'),
                    message: html,
                    wide: true
                });
            }
        }
    });
}
