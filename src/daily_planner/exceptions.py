class DailyPlannerError(Exception):
    """Base exception for Daily Planner."""


class ConfigurationError(DailyPlannerError):
    pass


class NotFoundError(DailyPlannerError):
    pass


class AmbiguousTaskError(DailyPlannerError):
    pass


class ParserError(DailyPlannerError):
    pass


class IntegrationError(DailyPlannerError):
    pass
