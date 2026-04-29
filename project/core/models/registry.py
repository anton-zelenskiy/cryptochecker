"""
Model registry for automatically importing all SQLAlchemy models.

This module imports all models from their respective packages, ensuring they're
registered with SQLAlchemy's Base metadata. This is useful for scripts and migrations
that need to resolve foreign key relationships.
"""

# Import all models from their packages
# This ensures they're registered with Base.metadata when the classes are defined



def register_all_models() -> None:
    """
    Register all SQLAlchemy models by importing them.

    Models are automatically registered with Base.metadata when imported.
    This function is idempotent - calling it multiple times is safe.

    Example:
        >>> from project.core.models.registry import register_all_models
        >>> register_all_models()
        >>> # Now all models are registered and can be used
    """
    # Models are already imported at module level, so this is a no-op
    # But we keep this function for backward compatibility
    pass


def get_all_models() -> list:
    """
    Get all registered SQLAlchemy models.

    Returns:
        List of all model classes that inherit from Base.

    Example:
        >>> from project.core.models.registry import get_all_models
        >>> models = get_all_models()
        >>> print([m.__name__ for m in models])
    """
    from project.core.models.base import Base

    if hasattr(Base.registry, '_class_registry'):
        return [
            cls
            for cls in Base.registry._class_registry.values()
            if isinstance(cls, type)
            and hasattr(cls, '__bases__')
            and Base in cls.__mro__
            and cls is not Base
        ]
    return []
