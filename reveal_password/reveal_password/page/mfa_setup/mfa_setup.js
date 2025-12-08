frappe.pages['mfa-setup'].on_page_load = function (wrapper) {
	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Multi-Factor Authentication Setup',
		single_column: true
	});

	let currentStep = 1;
	let mfaData = {};
	let backupCodes = [];

	// Main container
	$(wrapper).find('.layout-main-section').append(`
		<div class="mfa-setup-container" style="max-width: 800px; margin: 0 auto; padding: 40px 20px;">
			<div class="setup-progress" style="margin-bottom: 40px;">
				<div class="progress-steps" style="display: flex; justify-content: space-between; margin-bottom: 10px;">
					<div class="step" data-step="1">
						<div class="step-number active">1</div>
						<div class="step-label">Introduction</div>
					</div>
					<div class="step" data-step="2">
						<div class="step-number">2</div>
						<div class="step-label">Scan QR Code</div>
					</div>
					<div class="step" data-step="3">
						<div class="step-number">3</div>
						<div class="step-label">Verify</div>
					</div>
					<div class="step" data-step="4">
						<div class="step-number">4</div>
						<div class="step-label">Backup Codes</div>
					</div>
					<div class="step" data-step="5">
						<div class="step-number">5</div>
						<div class="step-label">Complete</div>
					</div>
				</div>
				<div class="progress-bar" style="height: 4px; background: #e2e8f0; border-radius: 2px;">
					<div class="progress-fill" style="height: 100%; background: #4CAF50; width: 20%; transition: width 0.3s;"></div>
				</div>
			</div>
			
			<div class="setup-content" id="setup-content"></div>
			
			<div class="setup-actions" style="margin-top: 30px; text-align: center;">
				<button class="btn btn-default" id="btn-back" style="display: none;">
					<i class="fa fa-arrow-left"></i> Back
				</button>
				<button class="btn btn-primary" id="btn-next">
					Next <i class="fa fa-arrow-right"></i>
				</button>
			</div>
		</div>
	`);

	// Add custom CSS
	frappe.dom.set_style(`
		.step-number {
			width: 40px;
			height: 40px;
			border-radius: 50%;
			background: #e2e8f0;
			color: #64748b;
			display: flex;
			align-items: center;
			justify-content: center;
			font-weight: 600;
			margin: 0 auto 8px;
		}
		.step-number.active {
			background: #4CAF50;
			color: white;
		}
		.step-number.completed {
			background: #4CAF50;
			color: white;
		}
		.step-label {
			font-size: 12px;
			color: #64748b;
			text-align: center;
		}
		.backup-code {
			font-family: 'Courier New', monospace;
			font-size: 16px;
			font-weight: 600;
			padding: 10px;
			background: #f8fafc;
			border: 1px solid #e2e8f0;
			border-radius: 4px;
			text-align: center;
		}
	`);

	function renderStep(step) {
		currentStep = step;
		updateProgress();

		const content = $('#setup-content');
		content.empty();

		switch (step) {
			case 1:
				renderIntroduction(content);
				break;
			case 2:
				renderQRCode(content);
				break;
			case 3:
				renderVerification(content);
				break;
			case 4:
				renderBackupCodes(content);
				break;
			case 5:
				renderCompletion(content);
				break;
		}

		// Update buttons
		$('#btn-back').toggle(step > 1 && step < 5);
		$('#btn-next').toggle(step < 5);
		$('#btn-next').text(step === 4 ? 'Finish' : 'Next');
	}

	function renderIntroduction(content) {
		content.html(`
			<div style="text-align: center;">
				<div style="font-size: 64px; margin-bottom: 20px;"><i class="fa fa-lock" style="color: #4CAF50;"></i></div>
				<h2>Secure Your Account with MFA</h2>
				<p style="font-size: 16px; color: #64748b; max-width: 600px; margin: 20px auto;">
					Multi-Factor Authentication adds an extra layer of security to your account by requiring
					a verification code from your mobile device in addition to your password.
				</p>
				
				<div style="margin: 40px 0; text-align: left; max-width: 500px; margin: 40px auto;">
					<h4>What you'll need:</h4>
					<ul style="font-size: 14px; color: #64748b;">
						<li>A smartphone or tablet</li>
						<li>An authenticator app (Google Authenticator, Authy, Microsoft Authenticator, etc.)</li>
						<li>About 2 minutes of your time</li>
					</ul>
				</div>
				
				<div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 15px; margin: 20px auto; max-width: 500px;">
					<strong><i class="fa fa-exclamation-triangle"></i> Important:</strong> Once enabled, you'll need your authenticator app to reveal passwords.
					Make sure to save your backup codes in a safe place!
				</div>
			</div>
		`);
	}

	function renderQRCode(content) {
		content.html('<div style="text-align: center;"><i class="fa fa-spinner fa-spin fa-3x"></i><p>Generating QR Code...</p></div>');

		frappe.call({
			method: 'reveal_password.reveal_password.doctype.mfa_secret.mfa_secret.setup_mfa',
			callback: function (r) {
				if (r.message) {
					mfaData = r.message;
					content.html(`
						<div style="text-align: center;">
							<h3>Scan this QR Code</h3>
							<p style="color: #64748b; margin-bottom: 30px;">
								Open your authenticator app and scan this QR code
							</p>
							
							<div style="background: white; padding: 20px; border-radius: 8px; display: inline-block; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
								<img src="${mfaData.qr_code}" alt="QR Code" style="width: 250px; height: 250px;">
							</div>
							
							<div style="margin-top: 30px;">
								<p style="color: #64748b; font-size: 14px;">Can't scan? Enter this code manually:</p>
								<div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; padding: 15px; margin: 10px auto; max-width: 400px;">
									<code style="font-size: 16px; font-weight: 600;">${mfaData.secret}</code>
								</div>
							</div>
						</div>
					`);
				}
			}
		});
	}

	function renderVerification(content) {
		content.html(`
			<div style="text-align: center;">
				<h3>Verify Your Setup</h3>
				<p style="color: #64748b; margin-bottom: 30px;">
					Enter the 6-digit code from your authenticator app
				</p>
				
				<div style="max-width: 300px; margin: 0 auto;">
					<input type="text" 
						   id="verification-code" 
						   class="form-control" 
						   placeholder="000000" 
						   maxlength="6"
						   style="font-size: 24px; text-align: center; letter-spacing: 8px; font-weight: 600;"
						   autofocus>
					<div id="verification-error" style="color: #ef4444; margin-top: 10px; display: none;"></div>
				</div>
				
				<p style="color: #64748b; font-size: 14px; margin-top: 20px;">
					The code changes every 30 seconds
				</p>
			</div>
		`);

		$('#verification-code').on('input', function () {
			$(this).val($(this).val().replace(/\D/g, ''));
		});
	}

	function renderBackupCodes(content) {
		content.html(`
			<div style="text-align: center;">
				<h3>Save Your Backup Codes</h3>
				<p style="color: #64748b; margin-bottom: 30px;">
					These codes can be used if you lose access to your authenticator app.<br>
					Each code can only be used once.
				</p>
				
				<div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 15px; margin: 20px auto; max-width: 500px;">
					<strong><i class="fa fa-exclamation-triangle"></i> Important:</strong> Save these codes in a secure location. You won't be able to see them again!
				</div>
				
				<div id="backup-codes-list" style="max-width: 400px; margin: 30px auto; display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
					${backupCodes.map(code => `<div class="backup-code">${code}</div>`).join('')}
				</div>
				
				<button class="btn btn-default" onclick="navigator.clipboard.writeText('${backupCodes.join('\\n')}'); frappe.show_alert('Copied to clipboard', 3);">
					<i class="fa fa-copy"></i> Copy All Codes
				</button>
				<button class="btn btn-default" onclick="window.print();">
					<i class="fa fa-print"></i> Print Codes
				</button>
			</div>
		`);
	}

	function renderCompletion(content) {
		content.html(`
			<div style="text-align: center;">
				<div style="font-size: 64px; margin-bottom: 20px;"><i class="fa fa-check-circle" style="color: #4CAF50;"></i></div>
				<h2>MFA Successfully Enabled!</h2>
				<p style="font-size: 16px; color: #64748b; max-width: 600px; margin: 20px auto;">
					Your account is now protected with Multi-Factor Authentication.
					You'll need to enter a code from your authenticator app when revealing passwords.
				</p>
				
				<div style="margin: 40px 0;">
					<button class="btn btn-primary btn-lg" onclick="frappe.set_route('/');">
						<i class="fa fa-home"></i> Go to Home
					</button>
				</div>
			</div>
		`);
	}

	function updateProgress() {
		const progress = (currentStep / 5) * 100;
		$('.progress-fill').css('width', progress + '%');

		$('.step-number').removeClass('active completed');
		$(`.step[data-step="${currentStep}"] .step-number`).addClass('active');

		for (let i = 1; i < currentStep; i++) {
			$(`.step[data-step="${i}"] .step-number`).addClass('completed');
		}
	}

	$('#btn-next').on('click', function () {
		if (currentStep === 3) {
			// Verify token
			const token = $('#verification-code').val();
			if (token.length !== 6) {
				$('#verification-error').text('Please enter a 6-digit code').show();
				return;
			}

			$(this).prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Verifying...');

			frappe.call({
				method: 'reveal_password.reveal_password.doctype.mfa_secret.mfa_secret.enable_mfa',
				args: { token: token },
				callback: function (r) {
					if (r.message && r.message.success) {
						backupCodes = r.message.backup_codes;
						renderStep(currentStep + 1);
					} else {
						$('#verification-error').text('Invalid code. Please try again.').show();
					}
					$('#btn-next').prop('disabled', false).html('Next <i class="fa fa-arrow-right"></i>');
				}
			});
		} else {
			renderStep(currentStep + 1);
		}
	});

	$('#btn-back').on('click', function () {
		renderStep(currentStep - 1);
	});

	// Initialize
	renderStep(1);
}
