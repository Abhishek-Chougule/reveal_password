frappe.call({
    method: "reveal_password.api.get_allowed_doctypes",
    callback: function (r) {
        if (r.message && Array.isArray(r.message)) {
            r.message.forEach(doctype_name => {
                frappe.ui.form.on(doctype_name, {
                    refresh(frm) {
                        add_password_toggle(frm);
                    }
                });
            });
        }
    }
});

function add_password_toggle(frm) {
    setTimeout(() => {
        (frm.fields || []).forEach(field => {
            if (field.df.fieldtype === 'Password') {
                const $input = field.$wrapper.find('input[data-fieldname="' + field.df.fieldname + '"]');
                if (!$input.length) return;

                let $toggle = field.$wrapper.find('.toggle-password');
                if (!$toggle.length) {
                    $toggle = $(`
                        <div class="toggle-password" style="margin-left: -30px; position: absolute; top: 50%; transform: translateY(-50%); cursor: pointer;">
                            <svg class="icon icon-sm" aria-hidden="true">
                                <use href="#icon-unhide"></use>
                            </svg>
                        </div>
                    `);
                    $input.after($toggle);
                }

                $toggle.removeClass('hidden');

                if ($toggle.attr('data-bound') === '1') return;
                $toggle.attr('data-bound', '1');

                let revealedPassword = "";
                let isVisible = false;

                $toggle.on('click', function () {
                    if (!revealedPassword) {
                        frappe.call({
                            method: "reveal_password.reveal.reveal_password",
                            args: {
                                doctype: frm.doctype,
                                docname: frm.docname,
                                fieldname: field.df.fieldname
                            },
                            callback: function (r) {
                                if (r.message) {
                                    revealedPassword = r.message;
                                    $input.attr('type', 'text').val(revealedPassword);
                                    isVisible = true;
                                } else {
                                    frappe.msgprint("You are not authorized to view this password.");
                                }
                            }
                        });
                    } else {
                        if (isVisible) {
                            $input.attr('type', 'password').val(revealedPassword);
                            isVisible = false;
                        } else {
                            $input.attr('type', 'text').val(revealedPassword);
                            isVisible = true;
                        }
                    }
                });
            }
        });
    }, 300);
}
