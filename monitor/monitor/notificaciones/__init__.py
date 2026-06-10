"""Motor de notificaciones (FASE 5): email, Telegram y webhook."""
from .motor import SEV_ORDEN, notificar, reintentar_pendientes, severidad_alcanza

__all__ = ["notificar", "reintentar_pendientes", "severidad_alcanza", "SEV_ORDEN"]
