### Reveal Password

Trusted Users Will get Password Handy


### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO
bench install-app reveal_password
```

### Features

- **Secure Reveal**: Permission-based password reveal for trusted users
- **Enhanced UI**: Modern interface with copy-to-clipboard and password strength indicator
- **Audit Logging**: Comprehensive tracking of all reveal attempts (success & failure)
- **Security**: Rate limiting to prevent brute force attacks
- **Configuration**: Whitelist-based DocType control
- **Integration**: Seamless integration with Frappe's encryption

### Usage

1. **Configure Trusted Users**: Add users to the "Trusted User" DocType
2. **Enable DocTypes**: Add DocTypes to "Reveal Allowed Doctypes"
3. **Reveal Passwords**: Click the eye icon on any password field in enabled DocTypes
4. **Monitor Access**: Check "Password Reveal Log" for a complete audit trail of all access attempts

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/reveal_password
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### License

mit

