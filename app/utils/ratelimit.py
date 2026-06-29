"""Rate-limit key helpers."""

from slowapi.util import get_remote_address


def client_ip(request) -> str:
    """IP real do cliente para rate limiting.

    Atras do Cloudflare Tunnel, request.client.host e o IP do tunnel — todos os
    clientes colapsariam numa mesma chave e um atacante nunca seria isolado. O
    Cloudflare envia o IP real do visitante em CF-Connecting-IP; e confiavel aqui
    porque o backend so e acessivel via o tunnel (nao ha rota direta para forjar).
    """
    return request.headers.get("CF-Connecting-IP") or get_remote_address(request)
