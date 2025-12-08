frappe.pages['reveal-links'].on_page_load = function (wrapper) {
    let page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'My Reveal Links',
        single_column: true
    });

    // Add action buttons
    page.set_primary_action('Create New Link', () => show_create_dialog(), 'add');
    page.set_secondary_action('Refresh', () => load_links(), 'refresh');

    // Main container
    $(wrapper).find('.layout-main-section').append(`
		<div class="reveal-links-container" style="padding: 20px;">
			<div class="stats-row" style="margin-bottom: 30px;">
				<div class="row">
					<div class="col-md-3">
						<div class="stat-card">
							<div class="stat-value" id="total-links">0</div>
							<div class="stat-label">Total Links</div>
						</div>
					</div>
					<div class="col-md-3">
						<div class="stat-card">
							<div class="stat-value" id="active-links">0</div>
							<div class="stat-label">Active Links</div>
						</div>
					</div>
					<div class="col-md-3">
						<div class="stat-card">
							<div class="stat-value" id="expired-links">0</div>
							<div class="stat-label">Expired</div>
						</div>
					</div>
					<div class="col-md-3">
						<div class="stat-card">
							<div class="stat-value" id="total-uses">0</div>
							<div class="stat-label">Total Uses</div>
						</div>
					</div>
				</div>
			</div>
			
			<div class="links-table-container">
				<table class="table table-bordered table-hover" id="links-table">
					<thead>
						<tr>
							<th>DocType</th>
							<th>Document</th>
							<th>Field</th>
							<th>Created</th>
							<th>Expires</th>
							<th>Uses</th>
							<th>Status</th>
							<th>Actions</th>
						</tr>
					</thead>
					<tbody id="links-tbody"></tbody>
				</table>
			</div>
		</div>
	`);

    // Add custom CSS
    frappe.dom.set_style(`
		.stat-card {
			background: var(--card-bg);
			border: 1px solid var(--border-color);
			border-radius: 8px;
			padding: 20px;
			text-align: center;
		}
		.stat-value {
			font-size: 32px;
			font-weight: 700;
			color: var(--text-color);
			margin-bottom: 5px;
		}
		.stat-label {
			font-size: 12px;
			color: var(--text-muted);
			text-transform: uppercase;
		}
		.link-url {
			font-family: 'Courier New', monospace;
			font-size: 12px;
			background: #f8fafc;
			padding: 4px 8px;
			border-radius: 4px;
			display: inline-block;
			max-width: 300px;
			overflow: hidden;
			text-overflow: ellipsis;
			white-space: nowrap;
		}
	`);

    function load_links() {
        frappe.call({
            method: 'reveal_password.reveal_password.doctype.temporary_reveal_link.temporary_reveal_link.get_my_links',
            callback: function (r) {
                if (r.message) {
                    render_links(r.message);
                    update_stats(r.message);
                }
            }
        });
    }

    function render_links(links) {
        const tbody = $('#links-tbody');
        tbody.empty();

        if (links.length === 0) {
            tbody.append(`
				<tr>
					<td colspan="8" style="text-align: center; padding: 40px; color: #64748b;">
						No links created yet. Click "Create New Link" to get started.
					</td>
				</tr>
			`);
            return;
        }

        links.forEach(link => {
            const now = new Date();
            const expires = new Date(link.expires_at);
            const isExpired = expires < now;
            const isExhausted = link.current_uses >= link.max_uses;
            const isActive = link.is_active && !isExpired && !isExhausted;

            let statusBadge = '';
            if (isActive) {
                statusBadge = '<span class="indicator-pill green">Active</span>';
            } else if (isExpired) {
                statusBadge = '<span class="indicator-pill red">Expired</span>';
            } else if (isExhausted) {
                statusBadge = '<span class="indicator-pill orange">Exhausted</span>';
            } else {
                statusBadge = '<span class="indicator-pill gray">Revoked</span>';
            }

            const row = `
				<tr>
					<td>${link.doctype_revealed}</td>
					<td>${link.document_name}</td>
					<td><code>${link.field_name}</code></td>
					<td>${frappe.datetime.comment_when(link.created_at)}</td>
					<td>${frappe.datetime.comment_when(link.expires_at)}</td>
					<td>${link.current_uses} / ${link.max_uses}</td>
					<td>${statusBadge}</td>
					<td>
						${isActive ? `
							<button class="btn btn-xs btn-default" onclick="copyLink('${link.link_id}')">
								<i class="fa fa-copy"></i> Copy
							</button>
							<button class="btn btn-xs btn-default" onclick="showQR('${link.link_id}')">
								<i class="fa fa-qrcode"></i> QR
							</button>
							<button class="btn btn-xs btn-danger" onclick="revokeLink('${link.link_id}')">
								<i class="fa fa-ban"></i> Revoke
							</button>
						` : `
							<button class="btn btn-xs btn-default" disabled>
								<i class="fa fa-ban"></i> Inactive
							</button>
						`}
					</td>
				</tr>
			`;
            tbody.append(row);
        });
    }

    function update_stats(links) {
        const total = links.length;
        const active = links.filter(l => {
            const now = new Date();
            const expires = new Date(l.expires_at);
            return l.is_active && expires > now && l.current_uses < l.max_uses;
        }).length;
        const expired = links.filter(l => new Date(l.expires_at) < new Date()).length;
        const totalUses = links.reduce((sum, l) => sum + l.current_uses, 0);

        $('#total-links').text(total);
        $('#active-links').text(active);
        $('#expired-links').text(expired);
        $('#total-uses').text(totalUses);
    }

    function show_create_dialog() {
        const dialog = new frappe.ui.Dialog({
            title: __('Create Temporary Reveal Link'),
            fields: [
                {
                    fieldname: 'doctype',
                    label: __('DocType'),
                    fieldtype: 'Link',
                    options: 'DocType',
                    reqd: 1,
                    onchange: function () {
                        const doctype = dialog.get_value('doctype');
                        if (doctype) {
                            // Fetch documents
                            dialog.fields_dict.docname.df.get_query = function () {
                                return {
                                    doctype: doctype
                                };
                            };
                            dialog.fields_dict.docname.refresh();
                        }
                    }
                },
                {
                    fieldname: 'docname',
                    label: __('Document'),
                    fieldtype: 'Dynamic Link',
                    options: 'doctype',
                    reqd: 1
                },
                {
                    fieldname: 'fieldname',
                    label: __('Field Name'),
                    fieldtype: 'Data',
                    reqd: 1,
                    description: __('Name of the password field')
                },
                {
                    fieldname: 'column_break',
                    fieldtype: 'Column Break'
                },
                {
                    fieldname: 'expires_in_hours',
                    label: __('Expires In (Hours)'),
                    fieldtype: 'Int',
                    default: 24,
                    reqd: 1
                },
                {
                    fieldname: 'max_uses',
                    label: __('Maximum Uses'),
                    fieldtype: 'Int',
                    default: 1,
                    reqd: 1
                }
            ],
            primary_action_label: __('Create Link'),
            primary_action: function (values) {
                frappe.call({
                    method: 'reveal_password.reveal_password.doctype.temporary_reveal_link.temporary_reveal_link.create_temporary_link',
                    args: values,
                    callback: function (r) {
                        if (r.message) {
                            dialog.hide();
                            show_link_created_dialog(r.message);
                            load_links();
                        }
                    }
                });
            }
        });
        dialog.show();
    }

    function show_link_created_dialog(data) {
        const dialog = new frappe.ui.Dialog({
            title: __('Link Created Successfully'),
            fields: [
                {
                    fieldtype: 'HTML',
                    options: `
						<div style="text-align: center; padding: 20px;">
							<div style="font-size: 48px; margin-bottom: 20px;"><i class="fa fa-check-circle" style="color: #4CAF50;"></i></div>
							<h3>Link Created Successfully!</h3>
							<p style="color: #64748b; margin: 20px 0;">Share this link to grant temporary access</p>
							
							<div style="background: #f8fafc; padding: 15px; border-radius: 8px; margin: 20px 0;">
								<input type="text" class="form-control" value="${data.url}" id="link-url" readonly>
								<button class="btn btn-primary btn-sm" style="margin-top: 10px;" onclick="
									navigator.clipboard.writeText('${data.url}');
									frappe.show_alert('Link copied!', 3);
								">
									<i class="fa fa-copy"></i> Copy Link
								</button>
							</div>
							
							${data.qr_code ? `
								<div style="margin: 20px 0;">
									<p style="font-weight: 600; margin-bottom: 10px;">QR Code</p>
									<img src="${data.qr_code}" style="max-width: 200px; border: 1px solid #e2e8f0; border-radius: 8px;">
								</div>
							` : ''}
							
							<div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 15px; margin-top: 20px; text-align: left;">
								<strong><i class="fa fa-exclamation-triangle"></i> Important:</strong>
								<ul style="margin: 10px 0 0 20px; font-size: 14px;">
									<li>Link expires: ${frappe.datetime.str_to_user(data.expires_at)}</li>
									<li>Maximum uses: ${data.max_uses}</li>
									<li>Anyone with this link can access the password</li>
									<li>You can revoke the link anytime from the links list</li>
								</ul>
							</div>
						</div>
					`
                }
            ]
        });
        dialog.show();
    }

    // Global functions for button actions
    window.copyLink = function (linkId) {
        const url = `${window.location.origin}/reveal-link/${linkId}`;
        navigator.clipboard.writeText(url).then(() => {
            frappe.show_alert({
                message: __('Link copied to clipboard'),
                indicator: 'green'
            }, 3);
        });
    };

    window.showQR = function (linkId) {
        frappe.msgprint({
            title: __('QR Code'),
            message: `<div style="text-align: center;">
				<p>Scan this QR code to access the link</p>
				<div id="qr-code-container"></div>
			</div>`,
            wide: true
        });
        // In production, generate QR code here
    };

    window.revokeLink = function (linkId) {
        frappe.confirm(
            __('Are you sure you want to revoke this link? This action cannot be undone.'),
            function () {
                frappe.call({
                    method: 'reveal_password.reveal_password.doctype.temporary_reveal_link.temporary_reveal_link.revoke_link',
                    args: { link_id: linkId },
                    callback: function (r) {
                        if (r.message && r.message.success) {
                            frappe.show_alert({
                                message: __('Link revoked successfully'),
                                indicator: 'green'
                            }, 3);
                            load_links();
                        }
                    }
                });
            }
        );
    };

    // Initialize
    load_links();
}
