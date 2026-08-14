class DominioError(Exception):
    """Error de reglas de negocio. La capa de interfaz lo traduce a HTTP 400."""


class SesionInvalidaError(DominioError):
    """La sesión no cumple las invariantes mínimas para persistirse."""


class NivelNoPermitidoError(DominioError):
    """El usuario intenta practicar un nivel HSK que aún no desbloqueó."""
