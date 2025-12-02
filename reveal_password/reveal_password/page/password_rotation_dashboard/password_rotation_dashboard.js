frappe.pages['password-rotation-dashboard'].on_page_load = function (wrapper) {
    let page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Password Rotation Dashboard',
        single_column: true
    });

    page.set_primary_action('New Policy', () => frappe.new_doc('Password Rotation Policy'), 'add');
    page.set_secondary_action('Refresh', () => load_dashboard(), 'refresh');

    $(wrapper).find('.layout-main-section').append(`
		<div class="rotation-dashboard" style="padding: 20px;">
			<div class="row" style="margin-bottom: 30px;">
				<div class="col-md-12">
					<div class="dashboard-card">
						<h4>Active Policies</h4>
						<div id="policies-list"></div>
					</div>
				</div>
			</div>
			
			<div class="row">
				<div class="col-md-12">
					<div class="dashboard-card">
						<h4>Recent Rotations</h4>
						<div id="history-list"></div>
					</div>
				</div>
			</div>
		</div>
	`);

    frappe.dom.set_style(`
		.dashboard-card {
			background: var(--card-bg);
			border: 1px solid var(--border-color);
			border-radius: 8px;
			padding: 20px;
			margin-bottom: 20px;
		}
		.policy-item {
			display: flex;
			justify-content: space-between;
			align-items: center;
			padding: 15px;
			border-bottom: 1px solid var(--border-color);
		}
		.policy-item:last-child {
			border-bottom: none;
		}
		.policy-info h5 {
			margin: 0 0 5px 0;
			font-weight: 600;
		}
		.policy-meta {
			font-size: 12px;
			color: var(--text-muted);
		}
	`);

    function load_dashboard() {
        load_policies();
        load_history();
    }

    function load_policies() {
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Password Rotation Policy',
                fields: ['name', 'policy_name', 'target_doctype', 'frequency', 'last_rotation', 'next_rotation', 'enabled'],
                filters: { enabled: 1 }
            },
            callback: function (r) {
                render_policies(r.message || []);
            }
        });
    }

    function render_policies(policies) {
        const container = $('#policies-list');
        container.empty();

        if (policies.length === 0) {
            container.html('<p class="text-muted">No active policies found.</p>');
            return;
        }

        policies.forEach(p => {
            const nextRun = p.next_rotation ? frappe.datetime.comment_when(p.next_rotation) : 'Not scheduled';
            const lastRun = p.last_rotation ? frappe.datetime.str_to_user(p.last_rotation) : 'Never';

            const html = `
				<div class="policy-item">
					<div class="policy-info">
						<h5><a href="/app/password-rotation-policy/${p.name}">${p.policy_name}</a></h5>
						<div class="policy-meta">
							Target: ${p.target_doctype} • Frequency: ${p.frequency}<br>
							Last Run: ${lastRun} • Next Run: ${nextRun}
						</div>
					</div>
					<div class="policy-actions">
						<button class="btn btn-xs btn-default" onclick="run_rotation('${p.name}')">
							Run Now
						</button>
					</div>
				</div>
			`;
            container.append(html);
        });
    }

    function load_history() {
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Password Rotation History',
                fields: ['name', 'policy', 'target_doctype', 'target_docname', 'rotation_date', 'status', 'error_message'],
                order_by: 'rotation_date desc',
                limit: 10
            },
            callback: function (r) {
                render_history(r.message || []);
            }
        });
    }

    function render_history(history) {
        const container = $('#history-list');
        container.empty();

        if (history.length === 0) {
            container.html('<p class="text-muted">No rotation history found.</p>');
            return;
        }

        const table = $(`<table class="table table-bordered table-hover">
			<thead>
				<tr>
					<th>Date</th>
					<th>Policy</th>
					<th>Target</th>
					<th>Status</th>
					<th>Details</th>
				</tr>
			</thead>
			<tbody></tbody>
		</table>`);

        history.forEach(h => {
            const statusColor = h.status === 'Success' ? 'green' : 'red';
            const row = `
				<tr>
					<td>${frappe.datetime.str_to_user(h.rotation_date)}</td>
					<td>${h.policy}</td>
					<td>${h.target_doctype} (${h.target_docname})</td>
					<td><span class="indicator-pill ${statusColor}">${h.status}</span></td>
					<td>${h.error_message || '-'}</td>
				</tr>
			`;
            table.find('tbody').append(row);
        });

        container.append(table);
    }

    window.run_rotation = function (policyName) {
        frappe.confirm(`Run rotation for policy <b>${policyName}</b> now?`, () => {
            frappe.call({
                method: 'reveal_password.reveal_password.doctype.password_rotation_policy.password_rotation_policy.run_rotation',
                args: { policy_name: policyName },
                freeze: true,
                callback: function (r) {
                    if (r.message) {
                        frappe.msgprint(`Rotation Completed.<br>Success: ${r.message.success}<br>Failed: ${r.message.failed}`);
                        load_dashboard();
                    }
                }
            });
        });
    };

    load_dashboard();
}
