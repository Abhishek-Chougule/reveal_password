frappe.pages['security-dashboard'].on_page_load = function (wrapper) {
	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Security Dashboard',
		single_column: true
	});

	// Add action buttons
	page.set_primary_action('Export Report', () => export_security_report(), 'download');
	page.set_secondary_action('Refresh', () => load_dashboard(), 'refresh');

	// Add filter
	page.add_field({
		fieldname: 'time_range',
		label: __('Time Range'),
		fieldtype: 'Select',
		options: ['Last 24 Hours', 'Last 7 Days', 'Last 30 Days', 'Last 90 Days'],
		default: 'Last 7 Days',
		change: () => load_dashboard()
	});

	// Main container
	$(wrapper).find('.layout-main-section').append(`
		<div class="security-dashboard-container" style="padding: 20px;">
			<!-- Alert Section -->
			<div id="alerts-section" style="margin-bottom: 30px;"></div>
			
			<!-- Key Metrics -->
			<div class="row" style="margin-bottom: 30px;">
				<div class="col-md-3">
					<div class="metric-card" id="total-sessions">
						<div class="metric-icon"><i class="fa fa-chart-bar"></i></div>
						<div class="metric-value">0</div>
						<div class="metric-label">Total Sessions</div>
					</div>
				</div>
				<div class="col-md-3">
					<div class="metric-card" id="suspicious-count">
						<div class="metric-icon"><i class="fa fa-exclamation-triangle"></i></div>
						<div class="metric-value">0</div>
						<div class="metric-label">Suspicious Activities</div>
					</div>
				</div>
				<div class="col-md-3">
					<div class="metric-card" id="unique-users">
						<div class="metric-icon"><i class="fa fa-users"></i></div>
						<div class="metric-value">0</div>
						<div class="metric-label">Active Users</div>
					</div>
				</div>
				<div class="col-md-3">
					<div class="metric-card" id="avg-anomaly">
						<div class="metric-icon"><i class="fa fa-bullseye"></i></div>
						<div class="metric-value">0</div>
						<div class="metric-label">Avg Anomaly Score</div>
					</div>
				</div>
			</div>
			
			<!-- Charts Row -->
			<div class="row" style="margin-bottom: 30px;">
				<div class="col-md-8">
					<div class="dashboard-card">
						<h4>Activity Timeline</h4>
						<div id="activity-timeline-chart"></div>
					</div>
				</div>
				<div class="col-md-4">
					<div class="dashboard-card">
						<h4>Top Users</h4>
						<div id="top-users-chart"></div>
					</div>
				</div>
			</div>
			
			<!-- Suspicious Activity Table -->
			<div class="row" style="margin-bottom: 30px;">
				<div class="col-md-12">
					<div class="dashboard-card">
						<h4>Suspicious Activities</h4>
						<div id="suspicious-activities-table"></div>
					</div>
				</div>
			</div>
			
			<!-- IP Analysis -->
			<div class="row">
				<div class="col-md-6">
					<div class="dashboard-card">
						<h4>Top IP Addresses</h4>
						<div id="top-ips-list"></div>
					</div>
				</div>
				<div class="col-md-6">
					<div class="dashboard-card">
						<h4>Device Analysis</h4>
						<div id="device-analysis-list"></div>
					</div>
				</div>
			</div>
		</div>
	`);

	// Add custom CSS
	frappe.dom.set_style(`
		.metric-card {
			background: var(--card-bg);
			border: 1px solid var(--border-color);
			border-radius: 8px;
			padding: 20px;
			text-align: center;
			transition: transform 0.2s;
		}
		.metric-card:hover {
			transform: translateY(-2px);
			box-shadow: 0 4px 12px rgba(0,0,0,0.1);
		}
		.metric-icon {
			font-size: 32px;
			margin-bottom: 10px;
		}
		.metric-value {
			font-size: 28px;
			font-weight: 700;
			color: var(--text-color);
			margin-bottom: 5px;
		}
		.metric-label {
			font-size: 12px;
			color: var(--text-muted);
			text-transform: uppercase;
			letter-spacing: 0.5px;
		}
		.dashboard-card {
			background: var(--card-bg);
			border: 1px solid var(--border-color);
			border-radius: 8px;
			padding: 20px;
			min-height: 300px;
		}
		.alert-box {
			padding: 15px;
			border-radius: 8px;
			margin-bottom: 15px;
			border-left: 4px solid;
		}
		.alert-critical {
			background: #fee;
			border-color: #f44;
		}
		.alert-warning {
			background: #fffbeb;
			border-color: #f59e0b;
		}
		.alert-info {
			background: #eff6ff;
			border-color: #3b82f6;
		}
	`);

	function load_dashboard() {
		const time_range = page.fields_dict.time_range.get_value();
		const days = get_days_from_range(time_range);

		// Load security metrics
		frappe.call({
			method: 'reveal_password.reveal_password.page.security_dashboard.security_dashboard.get_security_metrics',
			args: { days: days },
			callback: function (r) {
				if (r.message) {
					render_dashboard(r.message);
				}
			}
		});
	}

	function get_days_from_range(range) {
		const map = {
			'Last 24 Hours': 1,
			'Last 7 Days': 7,
			'Last 30 Days': 30,
			'Last 90 Days': 90
		};
		return map[range] || 7;
	}

	function render_dashboard(data) {
		// Render alerts
		render_alerts(data.alerts);

		// Update metrics
		$('#total-sessions .metric-value').text(data.total_sessions);
		$('#suspicious-count .metric-value').text(data.suspicious_count);
		$('#unique-users .metric-value').text(data.unique_users);
		$('#avg-anomaly .metric-value').text(data.avg_anomaly_score.toFixed(1));

		// Render activity timeline
		new frappe.Chart("#activity-timeline-chart", {
			data: {
				labels: data.timeline_labels,
				datasets: [
					{
						name: "Normal",
						values: data.timeline_normal
					},
					{
						name: "Suspicious",
						values: data.timeline_suspicious
					}
				]
			},
			type: 'bar',
			height: 250,
			colors: ['#4CAF50', '#f44336']
		});

		// Render top users
		new frappe.Chart("#top-users-chart", {
			data: {
				labels: data.top_users_labels,
				datasets: [{
					values: data.top_users_values
				}]
			},
			type: 'pie',
			height: 250,
			colors: ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981']
		});

		// Render suspicious activities table
		render_suspicious_table(data.suspicious_activities);

		// Render IP analysis
		render_ip_analysis(data.top_ips);

		// Render device analysis
		render_device_analysis(data.device_stats);
	}

	function render_alerts(alerts) {
		let html = '';

		alerts.forEach(alert => {
			const type_class = alert.severity === 'critical' ? 'alert-critical' :
				alert.severity === 'warning' ? 'alert-warning' : 'alert-info';
			html += `
				<div class="alert-box ${type_class}">
					<strong>${alert.title}</strong><br>
					${alert.message}
				</div>
			`;
		});

		$('#alerts-section').html(html || '<p style="color: #10b981;"><i class="fa fa-check"></i> No security alerts</p>');
	}

	function render_suspicious_table(activities) {
		let html = `<table class="table table-bordered table-hover">
			<thead>
				<tr>
					<th>User</th>
					<th>DocType</th>
					<th>IP Address</th>
					<th>Time</th>
					<th>Score</th>
					<th>Reasons</th>
				</tr>
			</thead>
			<tbody>`;

		activities.forEach(activity => {
			const score_color = activity.anomaly_score >= 75 ? 'red' :
				activity.anomaly_score >= 50 ? 'orange' : 'yellow';
			html += `
				<tr>
					<td>${activity.user}</td>
					<td>${activity.doctype_revealed}</td>
					<td><code>${activity.ip_address}</code></td>
					<td>${frappe.datetime.comment_when(activity.timestamp)}</td>
					<td><span class="indicator ${score_color}">${activity.anomaly_score}</span></td>
					<td style="font-size: 12px;">${activity.anomaly_reasons || 'N/A'}</td>
				</tr>
			`;
		});

		html += `</tbody></table>`;
		$('#suspicious-activities-table').html(html);
	}

	function render_ip_analysis(top_ips) {
		let html = '<div style="max-height: 300px; overflow-y: auto;">';

		top_ips.forEach(ip => {
			html += `
				<div style="padding: 10px; border-bottom: 1px solid var(--border-color);">
					<div style="display: flex; justify-content: space-between;">
						<code>${ip.ip_address}</code>
						<span class="badge badge-primary">${ip.count} sessions</span>
					</div>
					<div style="font-size: 12px; color: var(--text-muted); margin-top: 5px;">
						${ip.users.join(', ')}
					</div>
				</div>
			`;
		});

		html += '</div>';
		$('#top-ips-list').html(html);
	}

	function render_device_analysis(device_stats) {
		let html = '<div style="max-height: 300px; overflow-y: auto;">';

		device_stats.forEach(stat => {
			html += `
				<div style="padding: 10px; border-bottom: 1px solid var(--border-color);">
					<div style="display: flex; justify-content: space-between;">
						<strong>${stat.device_type}</strong>
						<span class="badge badge-secondary">${stat.count}</span>
					</div>
					<div style="font-size: 12px; color: var(--text-muted); margin-top: 5px;">
						${stat.percentage}% of total sessions
					</div>
				</div>
			`;
		});

		html += '</div>';
		$('#device-analysis-list').html(html);
	}

	function export_security_report() {
		const time_range = page.fields_dict.time_range.get_value();
		const days = get_days_from_range(time_range);

		frappe.call({
			method: 'reveal_password.reveal_password.page.security_dashboard.security_dashboard.export_security_report',
			args: { days: days },
			callback: function (r) {
				if (r.message) {
					// Download CSV
					const csv = r.message;
					const blob = new Blob([csv], { type: 'text/csv' });
					const url = window.URL.createObjectURL(blob);
					const a = document.createElement('a');
					a.href = url;
					a.download = `security_report_${frappe.datetime.now_date()}.csv`;
					a.click();

					frappe.show_alert({
						message: __('Report exported successfully'),
						indicator: 'green'
					}, 3);
				}
			}
		});
	}

	// Initialize
	load_dashboard();
}
