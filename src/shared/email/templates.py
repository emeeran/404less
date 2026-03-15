"""
Email Templates Module

@spec Shared infrastructure - email templates

Provides simple template rendering for emails.
"""

from string import Template
from typing import Any


# Plain text templates
TEMPLATES = {
    "verification.txt": Template("""
Hello,

Thank you for registering! Please verify your email address by clicking the link below:

$verify_url

This link will expire in 24 hours.

If you did not create an account, please ignore this email.

Thanks,
The Team
""".strip()),

    "verification.html": Template("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .button {
            display: inline-block;
            padding: 12px 24px;
            background-color: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 4px;
        }
        .footer { margin-top: 30px; font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Verify Your Email</h1>
        <p>Hello,</p>
        <p>Thank you for registering! Please verify your email address by clicking the button below:</p>
        <p>
            <a href="$verify_url" class="button">Verify Email</a>
        </p>
        <p>Or copy and paste this link into your browser:</p>
        <p><code>$verify_url</code></p>
        <p>This link will expire in 24 hours.</p>
        <p class="footer">
            If you did not create an account, please ignore this email.<br>
            &copy; The Team
        </p>
    </div>
</body>
</html>
""".strip()),

    "password_reset.txt": Template("""
Hello,

You requested to reset your password. Click the link below to proceed:

$reset_url

This link will expire in 1 hour.

If you did not request a password reset, please ignore this email.

Thanks,
The Team
""".strip()),
}


def render_template(template_name: str, **kwargs: Any) -> str:
    """
    Render an email template with the given variables.

    Args:
        template_name: Name of the template (e.g., "verification.txt")
        **kwargs: Variables to substitute in the template

    Returns:
        Rendered template string

    Raises:
        KeyError: If template not found
    """
    if template_name not in TEMPLATES:
        raise KeyError(f"Template not found: {template_name}")

    template = TEMPLATES[template_name]
    return template.substitute(**kwargs)
