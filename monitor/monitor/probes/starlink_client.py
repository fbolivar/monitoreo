"""Cliente gRPC del dish Starlink (parte aislada y dependiente de librerías).

El dish expone gRPC con server-reflection en 192.168.100.1:9200. Usamos `yagrc`
para invocar `SpaceX.API.Device.Device/Handle` con `get_status` sin necesidad de
compilar los .proto. Devuelve el mensaje `dish_get_status` crudo (protobuf), que
parsea (de forma pura) starlink.py.
"""
from __future__ import annotations


def obtener_status(host: str, port: int, timeout: float):
    """Consulta get_status al dish. Lanza excepción si no hay acceso/gRPC falla."""
    import grpc
    from yagrc import reflector as yagrc_reflector

    reflector = yagrc_reflector.GrpcReflectionClient()
    with grpc.insecure_channel(f"{host}:{port}") as channel:
        # Bloquea hasta que el canal esté listo (o expira el timeout).
        grpc.channel_ready_future(channel).result(timeout=timeout)
        reflector.load_protocols(channel, symbols=["SpaceX.API.Device.Device"])

        request_class = reflector.message_class("SpaceX.API.Device.Request")
        stub_class = reflector.service_stub_class("SpaceX.API.Device.Device")
        stub = stub_class(channel)

        response = stub.Handle(request_class(get_status={}), timeout=timeout)
        return response.dish_get_status
