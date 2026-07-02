"""Bloqueio de provedores de email descartavel (anti-farming de creditos gratis).

Nao e exaustivo (listas mudam), mas eleva a barra contra criacao em massa de contas
para farmar os creditos de boas-vindas. A defesa robusta seria captcha no cadastro
(pendente). Para adicionar dominios, basta inclui-los no set abaixo.
"""

_DISPOSABLE_DOMAINS = frozenset(
    {
        "mailinator.com",
        "guerrillamail.com",
        "guerrillamail.info",
        "sharklasers.com",
        "10minutemail.com",
        "10minutemail.net",
        "tempmail.com",
        "temp-mail.org",
        "temp-mail.io",
        "tempmail.net",
        "throwawaymail.com",
        "yopmail.com",
        "getnada.com",
        "nada.email",
        "trashmail.com",
        "maildrop.cc",
        "dispostable.com",
        "fakeinbox.com",
        "mailnesia.com",
        "mintemail.com",
        "mohmal.com",
        "spamgourmet.com",
        "tempinbox.com",
        "emailondeck.com",
        "burnermail.io",
        "mail-temp.com",
        "discard.email",
        "33mail.com",
        "mailcatch.com",
        "tempr.email",
        "moakt.com",
        "luxusmail.org",
        "1secmail.com",
        "1secmail.org",
        "1secmail.net",
        "guerrillamailblock.com",
        "grr.la",
        "sharklasers.net",
        "spam4.me",
        "tempmailo.com",
        "email-fake.com",
        "fakemail.net",
        "fakemailgenerator.com",
        "mailpoof.com",
        "smailpro.com",
        "dropmail.me",
        "inboxbear.com",
        "shortmail.net",
        "tmpmail.org",
        "tmpmail.net",
        "mail7.io",
        "tempmail.digital",
        "tempmail.win",
        "emailtemporal.org",
    }
)


def is_disposable_email(email: str) -> bool:
    """True se o dominio do email for de um provedor descartavel conhecido."""
    domain = email.rsplit("@", 1)[-1].strip().lower()
    return domain in _DISPOSABLE_DOMAINS
