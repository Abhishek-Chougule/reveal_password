frappe.pages['password-analytics'].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Password Analytics',
        single_column: true
    });

    // Add refresh button
    page.set_secondary_action('Refresh', () => load_analytics(), 'refresh');

    // Container for charts
    $(wrapper).find('.layout-main-section').append(`
        <div class="analytics-container" style="padding: 20px;">
            <div class="row">
                <div class="col-md-3">
                    <div class="dashboard-stat-box" id="total-reveals">
                        <span class="stat-title">Total Reveals</span>
                        <h3 class="stat-value">0</h3>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="dashboard-stat-box" id="success-rate">
                        <span class="stat-title">Success Rate</span>
                        <h3 class="stat-value">0%</h3>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="dashboard-stat-box" id="active-users">
                        <span class="stat-title">Active Users</span>
                        <h3 class="stat-value">0</h3>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="dashboard-stat-box" id="failed-attempts">
                        <span class="stat-title">Failed Attempts</span>
                        <h3 class="stat-value" style="color: var(--red-500);">0</h3>
                    </div>
                </div>
            </div>
            <div class="row" style="margin-top: 30px;">
                <div class="col-md-8">
                    <div class="chart-box">
                        <h4>Reveal Trend (Last 30 Days)</h4>
                        <div id="reveal-trend-chart"></div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="chart-box">
                        <h4>Top Doctypes</h4>
                        <div id="doctype-dist-chart"></div>
                    </div>
                </div>
            </div>
             <div class="row" style="margin-top: 30px;">
                <div class="col-md-12">
                     <div class="chart-box">
                        <h4>Recent Activity</h4>
                        <div id="recent-activity-list"></div>
                    </div>
                </div>
            </div>
        </div>
    `);

    // Add custom CSS
    frappe.dom.set_style(`
        .dashboard-stat-box {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
            text-align: center;
        }
        .stat-title {
            color: var(--text-muted);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .stat-value {
            font-size: 28px;
            font-weight: 700;
            margin-top: 10px;
            margin-bottom: 0;
        }
        .chart-box {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
            min-height: 300px;
        }
    `);

    function load_analytics() {
        frappe.call({
            method: "reveal_password.reveal.get_reveal_statistics",
            args: { period: "monthly" },
            callback: function (r) {
                if (r.message) {
                    update_dashboard(r.message);
                }
            }
        });
    }

    function update_dashboard(data) {
        // Update stats
        $('#total-reveals .stat-value').text(data.total_reveals);
        $('#success-rate .stat-value').text(data.success_rate + '%');
        $('#active-users .stat-value').text(data.active_users);
        $('#failed-attempts .stat-value').text(data.failed_attempts);

        // Render Trend Chart
        new frappe.Chart("#reveal-trend-chart", {
            data: {
                labels: data.trend_labels,
                datasets: [
                    {
                        name: "Reveals",
                        chartType: "line",
                        values: data.trend_values
                    }
                ]
            },
            type: 'line',
            height: 250,
            colors: ['#574b90']
        });

        // Render DocType Chart
        new frappe.Chart("#doctype-dist-chart", {
            data: {
                labels: data.doctype_labels,
                datasets: [
                    {
                        name: "DocTypes",
                        chartType: "pie",
                        values: data.doctype_values
                    }
                ]
            },
            type: 'donut',
            height: 250,
            colors: ['#74b9ff', '#55efc4', '#a29bfe', '#ffeaa7']
        });

        // Render Recent Activity
        let activity_html = `<table class="table table-bordered table-hover">
            <thead>
                <tr>
                    <th>User</th>
                    <th>DocType</th>
                    <th>Document</th>
                    <th>Time</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>`;

        data.recent_activity.forEach(log => {
            const status_color = log.success ? 'green' : 'red';
            activity_html += `
                <tr>
                    <td>${log.user}</td>
                    <td>${log.doctype}</td>
                    <td>${log.docname}</td>
                    <td>${frappe.datetime.comment_when(log.timestamp)}</td>
                    <td><span class="indicator ${status_color}">${log.success ? 'Success' : 'Failed'}</span></td>
                </tr>
            `;
        });

        activity_html += `</tbody></table>`;
        $('#recent-activity-list').html(activity_html);
    }

    load_analytics();
}
