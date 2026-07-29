class GoldenShieldError(Exception):
    """خطأ أساسي في النظام."""


class ConfigurationError(GoldenShieldError):
    """خطأ في تحميل أو قراءة الإعدادات."""


class ExchangeConnectionError(GoldenShieldError):
    """خطأ في الاتصال بمنصة التداول."""


class ExecutionError(GoldenShieldError):
    """خطأ أثناء تنفيذ الصفقة."""
