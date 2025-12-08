/**
 * Enhanced Password Reveal Manager
 * 
 * Modern ES6+ implementation with:
 * - MutationObserver for reliable field detection
 * - Copy-to-clipboard functionality
 * - Password strength indicator
 * - Loading states and animations
 * - Keyboard shortcuts
 * - Intelligent caching
 * - Error handling
 * 
 * @author Abhishek Chougule
 * @version 2.0
 */

class PasswordRevealManager {
	constructor() {
		this.allowedDoctypes = new Set();
		this.revealCache = new Map();
		this.observers = new Map();
		this.CACHE_TTL = 60000; // 1 minute
		this.AUTO_HIDE_DELAY = 30000; // 30 seconds

		this.init();
	}

	/**
	 * Initialize the manager
	 */
	async init() {
		try {
			await this.loadAllowedDoctypes();
			this.setupDoctypeHandlers();
			this.setupGlobalKeyboardShortcuts();
			console.log('Password Reveal Manager initialized successfully');
		} catch (error) {
			console.error('Failed to initialize Password Reveal Manager:', error);
			this.showAlert('Failed to initialize password reveal', 'red');
		}
	}

	/**
	 * Load allowed DocTypes from backend
	 */
	async loadAllowedDoctypes() {
		try {
			const response = await frappe.call({
				method: "reveal_password.api.get_allowed_doctypes"
			});

			if (response.message && Array.isArray(response.message)) {
				response.message.forEach(dt => this.allowedDoctypes.add(dt));
				console.log(`Loaded ${this.allowedDoctypes.size} allowed DocTypes`);
			}
		} catch (error) {
			console.error('Error loading allowed doctypes:', error);
			throw error;
		}
	}

	/**
	 * Set up form handlers for allowed DocTypes
	 */
	setupDoctypeHandlers() {
		this.allowedDoctypes.forEach(doctype => {
			frappe.ui.form.on(doctype, {
				refresh: (frm) => this.handleFormRefresh(frm)
			});
		});
	}

	/**
	 * Handle form refresh event
	 */
	handleFormRefresh(frm) {
		// Clean up previous observer if exists
		const observerKey = `${frm.doctype}:${frm.docname}`;
		if (this.observers.has(observerKey)) {
			this.observers.get(observerKey).disconnect();
		}

		// Use MutationObserver for reliable field detection
		const observer = new MutationObserver(() => {
			this.enhancePasswordFields(frm);
		});

		const targetNode = frm.wrapper && frm.wrapper[0];
		if (targetNode) {
			observer.observe(targetNode, {
				childList: true,
				subtree: true
			});
			this.observers.set(observerKey, observer);
		} else {
			// If wrapper is not available, just run enhancement once
			console.warn('Password Reveal: Form wrapper not found for observation');
		}



		// Initial enhancement
		this.enhancePasswordFields(frm);
	}

	/**
	 * Enhance all password fields in the form
	 */
	enhancePasswordFields(frm) {
		const passwordFields = frm.fields.filter(
			field => field.df.fieldtype === 'Password'
		);

		passwordFields.forEach(field => {
			this.enhancePasswordField(frm, field);
		});
	}

	/**
	 * Enhance a single password field
	 */
	enhancePasswordField(frm, field) {
		const $wrapper = field.$wrapper;
		const $input = $wrapper.find(`input[data-fieldname="${field.df.fieldname}"]`);

		if (!$input.length || $wrapper.find('.password-reveal-controls').length) {
			return;
		}

		// Create control panel
		const $controls = this.createControlPanel(frm, field, $input);

		// Insert after input
		const $inputWrapper = $input.parent();
		$inputWrapper.css('position', 'relative');
		$inputWrapper.append($controls);
	}

	/**
	 * Create enhanced control panel
	 */
	createControlPanel(frm, field, $input) {
		const $controls = $(`
			<div class="password-reveal-controls">
				<button class="btn btn-xs btn-reveal" type="button" title="${__('Reveal Password (Ctrl+Shift+P)')}">
					<i class="fa fa-eye"></i>
					<span class="btn-text">${__('Reveal')}</span>
				</button>
				<button class="btn btn-xs btn-copy" type="button" style="display: none;" title="${__('Copy to Clipboard')}">
					<i class="fa fa-copy"></i>
					<span class="btn-text">${__('Copy')}</span>
				</button>
				<div class="password-strength" style="display: none;">
					<div class="strength-bar-container">
						<div class="strength-bar"></div>
					</div>
					<span class="strength-text"></span>
				</div>
			</div>
		`);

		this.attachEventHandlers(frm, field, $input, $controls);

		return $controls;
	}

	/**
	 * Attach event handlers to controls
	 */
	attachEventHandlers(frm, field, $input, $controls) {
		const $revealBtn = $controls.find('.btn-reveal');
		const $copyBtn = $controls.find('.btn-copy');
		let isRevealed = false;
		let revealedPassword = null;
		let autoHideTimeout = null;

		// Reveal button click
		$revealBtn.on('click', async () => {
			if (isRevealed) {
				this.hidePassword($input, $revealBtn, $copyBtn, $controls);
				isRevealed = false;
				revealedPassword = null;
				if (autoHideTimeout) {
					clearTimeout(autoHideTimeout);
				}
			} else {
				const password = await this.revealPassword(
					frm, field, $input, $revealBtn, $controls
				);
				if (password !== null) {
					revealedPassword = password;
					isRevealed = true;
					$copyBtn.show();

					if (password) {
						this.showPasswordStrength($controls, password);
					}

					// Schedule auto-hide
					autoHideTimeout = setTimeout(() => {
						this.hidePassword($input, $revealBtn, $copyBtn, $controls);
						isRevealed = false;
						revealedPassword = null;
					}, this.AUTO_HIDE_DELAY);
				}
			}
		});

		// Copy button click
		$copyBtn.on('click', () => {
			if (revealedPassword) {
				this.copyToClipboard(revealedPassword);
			}
		});

		// Store reference for keyboard shortcuts
		$input.data('reveal-controls', { $revealBtn, isRevealed, field });
	}

	/**
	 * Reveal password with comprehensive error handling
	 */
	async revealPassword(frm, field, $input, $btn, $controls) {
		// Check cache first
		const cacheKey = `${frm.doctype}:${frm.docname}:${field.df.fieldname}`;
		const cached = this.revealCache.get(cacheKey);

		if (cached && (Date.now() - cached.timestamp < this.CACHE_TTL)) {
			$input.attr('type', 'text').val(cached.password);
			this.updateButtonState($btn, true);
			return cached.password;
		}

		// Show loading state
		this.setLoadingState($btn, true);

		try {
			const response = await frappe.call({
				method: "reveal_password.reveal.reveal_password",
				args: {
					doctype: frm.doctype,
					docname: frm.docname,
					fieldname: field.df.fieldname
				}
			});

			if (response.message !== undefined) {
				const password = response.message;

				// Update cache
				this.revealCache.set(cacheKey, {
					password: password,
					timestamp: Date.now()
				});

				// Update UI
				$input.attr('type', 'text').val(password);
				this.updateButtonState($btn, true);

				// Show success notification
				this.showAlert(__('Password revealed successfully'), 'green', 3);

				return password;
			}
		} catch (error) {
			console.error('Password reveal failed:', error);

			let errorMessage = __('Failed to reveal password');
			if (error.message) {
				errorMessage = error.message;
			}

			this.showAlert(errorMessage, 'red', 5);
			return null;
		} finally {
			this.setLoadingState($btn, false);
		}
	}

	/**
	 * Hide password
	 */
	hidePassword($input, $btn, $copyBtn, $controls) {
		$input.attr('type', 'password').val('••••••••');
		this.updateButtonState($btn, false);
		$copyBtn.hide();
		$controls.find('.password-strength').hide();
	}

	/**
	 * Update button state
	 */
	updateButtonState($btn, isRevealed) {
		const iconClass = isRevealed ? 'fa-eye-slash' : 'fa-eye';
		const text = isRevealed ? __('Hide') : __('Reveal');

		$btn.find('i').attr('class', 'fa ' + iconClass);
		$btn.find('.btn-text').text(text);
		$btn.removeClass('btn-primary').addClass(isRevealed ? 'btn-secondary' : 'btn-primary');
	}

	/**
	 * Set loading state
	 */
	setLoadingState($btn, isLoading) {
		if (isLoading) {
			$btn.prop('disabled', true);
			$btn.find('.btn-text').text(__('Loading...'));
			$btn.addClass('loading');
		} else {
			$btn.prop('disabled', false);
			$btn.removeClass('loading');
		}
	}

	/**
	 * Copy text to clipboard
	 */
	async copyToClipboard(text) {
		try {
			await navigator.clipboard.writeText(text);
			this.showAlert(__('Password copied to clipboard'), 'green', 2);
		} catch (err) {
			console.error('Copy failed:', err);

			// Fallback method
			const $temp = $('<textarea>');
			$('body').append($temp);
			$temp.val(text).select();
			document.execCommand('copy');
			$temp.remove();

			this.showAlert(__('Password copied to clipboard'), 'green', 2);
		}
	}

	/**
	 * Show password strength indicator
	 */
	showPasswordStrength($controls, password) {
		const strength = this.calculatePasswordStrength(password);
		const $strengthDiv = $controls.find('.password-strength');
		const $bar = $strengthDiv.find('.strength-bar');
		const $text = $strengthDiv.find('.strength-text');

		$strengthDiv.show();
		$bar.css({
			width: `${strength.score}%`,
			backgroundColor: strength.color
		});
		$text.text(strength.label);
	}

	/**
	 * Calculate password strength
	 */
	calculatePasswordStrength(password) {
		let score = 0;

		// Length
		if (password.length >= 8) score += 20;
		if (password.length >= 12) score += 20;
		if (password.length >= 16) score += 10;

		// Character types
		if (/[a-z]/.test(password)) score += 15;
		if (/[A-Z]/.test(password)) score += 15;
		if (/[0-9]/.test(password)) score += 10;
		if (/[^a-zA-Z0-9]/.test(password)) score += 10;

		let label, color;
		if (score < 40) {
			label = __('Weak');
			color = '#ff4444';
		} else if (score < 70) {
			label = __('Medium');
			color = '#ffaa00';
		} else {
			label = __('Strong');
			color = '#00cc44';
		}

		return { score: Math.min(score, 100), label, color };
	}

	/**
	 * Set up global keyboard shortcuts
	 */
	setupGlobalKeyboardShortcuts() {
		$(document).on('keydown', (e) => {
			// Ctrl+Shift+P to reveal
			if (e.ctrlKey && e.shiftKey && e.key === 'P') {
				e.preventDefault();

				const $focused = $(document.activeElement);
				if ($focused.is('input[type="password"]')) {
					const controls = $focused.data('reveal-controls');
					if (controls && controls.$revealBtn) {
						controls.$revealBtn.click();
					}
				}
			}
		});
	}

	/**
	 * Show alert notification
	 */
	showAlert(message, indicator = 'blue', duration = 3) {
		frappe.show_alert({
			message: message,
			indicator: indicator
		}, duration);
	}

	/**
	 * Clean up resources
	 */
	destroy() {
		this.observers.forEach(observer => observer.disconnect());
		this.observers.clear();
		this.revealCache.clear();
		$(document).off('keydown');
	}
}

// Initialize the manager when DOM is ready
$(document).ready(() => {
	window.passwordRevealManager = new PasswordRevealManager();
});
