frappe.pages['bulk-permission-manager'].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Bulk Permission Manager',
        single_column: true
    });

    // Add action buttons
    page.set_primary_action('Apply Permissions', () => apply_bulk_permissions(), 'check');
    page.set_secondary_action('Refresh', () => load_permission_matrix(), 'refresh');

    // Container for the permission matrix
    $(wrapper).find('.layout-main-section').append(`
		<div class="bulk-permission-container" style="padding: 20px;">
			<div class="filter-section" style="margin-bottom: 30px;">
				<div class="row">
					<div class="col-md-4">
						<div class="form-group">
							<label>DocType</label>
							<select class="form-control" id="filter-doctype">
								<option value="">All DocTypes</option>
							</select>
						</div>
					</div>
					<div class="col-md-4">
						<div class="form-group">
							<label>Role</label>
							<select class="form-control" id="filter-role">
								<option value="">All Roles</option>
							</select>
						</div>
					</div>
					<div class="col-md-4">
						<div class="form-group">
							<label>&nbsp;</label>
							<button class="btn btn-default btn-block" id="apply-filter">
								<i class="fa fa-filter"></i> Apply Filter
							</button>
						</div>
					</div>
				</div>
			</div>
			
			<div class="permission-matrix-section">
				<h4>Permission Matrix</h4>
				<div id="permission-matrix-table"></div>
			</div>
		</div>
	`);

    // Add custom CSS
    frappe.dom.set_style(`
		.permission-cell {
			text-align: center;
			vertical-align: middle !important;
		}
		.permission-checkbox {
			transform: scale(1.3);
			cursor: pointer;
		}
		.doctype-header {
			background-color: var(--bg-blue);
			font-weight: 600;
			padding: 10px;
		}
		.field-row {
			background-color: var(--card-bg);
		}
		.field-row:hover {
			background-color: var(--bg-light-gray);
		}
	`);

    // Load initial data
    load_filters();
    load_permission_matrix();

    // Event handlers
    $('#apply-filter').on('click', function () {
        load_permission_matrix();
    });

    function load_filters() {
        // Load DocTypes with password fields
        frappe.call({
            method: 'reveal_password.reveal_password.page.bulk_permission_manager.bulk_permission_manager.get_doctypes_with_password_fields',
            callback: function (r) {
                if (r.message) {
                    r.message.forEach(dt => {
                        $('#filter-doctype').append(`<option value="${dt}">${dt}</option>`);
                    });
                }
            }
        });

        // Load Roles
        frappe.call({
            method: 'frappe.core.doctype.role.role.get_roles',
            callback: function (r) {
                if (r.message) {
                    r.message.forEach(role => {
                        $('#filter-role').append(`<option value="${role}">${role}</option>`);
                    });
                }
            }
        });
    }

    function load_permission_matrix() {
        const doctype_filter = $('#filter-doctype').val();
        const role_filter = $('#filter-role').val();

        frappe.call({
            method: 'reveal_password.reveal_password.page.bulk_permission_manager.bulk_permission_manager.get_permission_matrix',
            args: {
                doctype: doctype_filter,
                role: role_filter
            },
            callback: function (r) {
                if (r.message) {
                    render_permission_matrix(r.message);
                }
            }
        });
    }

    function render_permission_matrix(data) {
        let html = '<table class="table table-bordered table-hover">';
        html += '<thead><tr>';
        html += '<th>DocType</th>';
        html += '<th>Field</th>';

        // Get unique roles
        const roles = [...new Set(data.map(d => d.role))];
        roles.forEach(role => {
            html += `<th class="permission-cell">${role}</th>`;
        });
        html += '</tr></thead><tbody>';

        // Group by DocType and Field
        const grouped = {};
        data.forEach(item => {
            const key = `${item.doctype}::${item.field}`;
            if (!grouped[key]) {
                grouped[key] = {
                    doctype: item.doctype,
                    field: item.field,
                    permissions: {}
                };
            }
            grouped[key].permissions[item.role] = item.can_reveal;
        });

        // Render rows
        Object.values(grouped).forEach(item => {
            html += '<tr class="field-row">';
            html += `<td><strong>${item.doctype}</strong></td>`;
            html += `<td><code>${item.field}</code></td>`;

            roles.forEach(role => {
                const checked = item.permissions[role] ? 'checked' : '';
                html += `<td class="permission-cell">
					<input type="checkbox" class="permission-checkbox" 
						data-doctype="${item.doctype}" 
						data-field="${item.field}" 
						data-role="${role}" 
						${checked}>
				</td>`;
            });
            html += '</tr>';
        });

        html += '</tbody></table>';
        $('#permission-matrix-table').html(html);
    }

    function apply_bulk_permissions() {
        const permissions = [];

        $('.permission-checkbox').each(function () {
            permissions.push({
                doctype: $(this).data('doctype'),
                field: $(this).data('field'),
                role: $(this).data('role'),
                can_reveal: $(this).is(':checked') ? 1 : 0
            });
        });

        frappe.call({
            method: 'reveal_password.reveal_password.page.bulk_permission_manager.bulk_permission_manager.save_bulk_permissions',
            args: {
                permissions: permissions
            },
            callback: function (r) {
                if (r.message) {
                    frappe.show_alert({
                        message: __('Permissions updated successfully'),
                        indicator: 'green'
                    }, 5);
                    load_permission_matrix();
                }
            }
        });
    }
}
