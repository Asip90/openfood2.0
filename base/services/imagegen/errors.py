class ImageGenError(Exception):
    """Échec de génération d'image (config, réseau, réponse invalide)."""


class QuotaExceeded(ImageGenError):
    """Quota quotidien du restaurant atteint."""


class Disabled(ImageGenError):
    """Fonctionnalité désactivée globalement."""
