"""
Email Template Engine Module

@spec Shared infrastructure - email template abstraction

Provides an abstract interface for template rendering,
enabling easier testing and future template engine swaps.
"""

from abc import ABC, abstractmethod
from string import Template
from typing import Any, Dict, Optional


class TemplateEngine(ABC):
    """
    Abstract base class for template rendering engines.

    Allows swapping template backends (string.Template, Jinja2, etc.)
    without changing email service code.
    """

    @abstractmethod
    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Render a template with the given context.

        Args:
            template_name: Name of the template to render
            context: Dictionary of variables for template substitution

        Returns:
            Rendered template string

        Raises:
            TemplateNotFoundError: If template doesn't exist
            TemplateRenderError: If rendering fails
        """
        pass

    @abstractmethod
    def render_string(self, template_string: str, context: Dict[str, Any]) -> str:
        """
        Render a template string directly.

        Args:
            template_string: Raw template content
            context: Dictionary of variables for substitution

        Returns:
            Rendered string
        """
        pass


class TemplateNotFoundError(Exception):
    """Raised when a template cannot be found."""
    pass


class TemplateRenderError(Exception):
    """Raised when template rendering fails."""
    pass


class StringTemplateEngine(TemplateEngine):
    """
    Simple template engine using Python's string.Template.

    Good for basic templates with $variable substitution.
    """

    def __init__(self, templates: Optional[Dict[str, str]] = None):
        """
        Initialize with optional template dictionary.

        Args:
            templates: Dictionary mapping template names to template strings
        """
        self._templates: Dict[str, str] = templates or {}

    def register_template(self, name: str, content: str) -> None:
        """
        Register a template.

        Args:
            name: Template name for later lookup
            content: Template string content
        """
        self._templates[name] = content

    def register_templates(self, templates: Dict[str, str]) -> None:
        """
        Register multiple templates at once.

        Args:
            templates: Dictionary of template name -> content
        """
        self._templates.update(templates)

    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Render a registered template.

        Args:
            template_name: Name of registered template
            context: Variables for substitution

        Returns:
            Rendered string

        Raises:
            TemplateNotFoundError: If template not registered
        """
        if template_name not in self._templates:
            raise TemplateNotFoundError(f"Template not found: {template_name}")

        return self.render_string(self._templates[template_name], context)

    def render_string(self, template_string: str, context: Dict[str, Any]) -> str:
        """
        Render a template string using string.Template.

        Args:
            template_string: Template content with $variable placeholders
            context: Variables for substitution

        Returns:
            Rendered string

        Raises:
            TemplateRenderError: If substitution fails
        """
        try:
            template = Template(template_string)
            return template.substitute(**context)
        except KeyError as e:
            raise TemplateRenderError(f"Missing template variable: {e}")
        except Exception as e:
            raise TemplateRenderError(f"Template rendering failed: {e}")


class InMemoryTemplateEngine(StringTemplateEngine):
    """
    In-memory template engine with pre-loaded templates.

    Useful for testing and small applications.
    """

    # Default email templates
    DEFAULT_TEMPLATES = {
        "verification.txt": """
Hello,

Thank you for registering! Please verify your email address by visiting:

$verify_url

This link will expire in 24 hours.

If you did not create an account, please ignore this email.

Thanks,
The Team
""".strip(),

        "verification.html": """
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
""".strip(),

        "password_reset.txt": """
Hello,

You requested to reset your password. Click the link below to proceed:

$reset_url

This link will expire in 1 hour.

If you did not request a password reset, please ignore this email.

Thanks,
The Team
""".strip(),
    }

    def __init__(self, templates: Optional[Dict[str, str]] = None):
        """
        Initialize with default templates, optionally extended.

        Args:
            templates: Additional templates to register
        """
        super().__init__({**self.DEFAULT_TEMPLATES, **(templates or {})})


# Global template engine instance
_template_engine: Optional[TemplateEngine] = None


def get_template_engine() -> TemplateEngine:
    """
    Get the global template engine instance.

    Returns a default InMemoryTemplateEngine if not configured.

    Returns:
        TemplateEngine instance
    """
    global _template_engine
    if _template_engine is None:
        _template_engine = InMemoryTemplateEngine()
    return _template_engine


def set_template_engine(engine: TemplateEngine) -> None:
    """
    Set the global template engine instance.

    Use this for dependency injection in tests or custom configurations.

    Args:
        engine: TemplateEngine instance to use globally
    """
    global _template_engine
    _template_engine = engine


def render_email_template(template_name: str, **context: Any) -> str:
    """
    Convenience function to render an email template.

    Args:
        template_name: Name of template to render
        **context: Variables for template substitution

    Returns:
        Rendered template string
    """
    return get_template_engine().render(template_name, context)
