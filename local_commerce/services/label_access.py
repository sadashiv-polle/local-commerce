"""Purpose-bound signatures for read-only packing label summaries."""
import hashlib
import hmac


def signature(secret, order):
    if not secret:
        raise ValueError('Site encryption key is required for label links')
    return hmac.new(str(secret).encode(), ('packing-label-v1:' + order).encode(), hashlib.sha256).hexdigest()


def valid_signature(secret, order, token):
    return bool(secret and isinstance(token, str) and len(token) == 64 and token.isascii()
                and hmac.compare_digest(signature(secret, order), token))
