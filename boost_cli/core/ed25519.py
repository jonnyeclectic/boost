"""Ed25519 signature *verification*, pure standard library.

boost's runtime is dependency-free, so it cannot lean on ``cryptography`` or a
``libsodium`` binding to check a signature. This is a compact, verify-only
Ed25519 implementation following RFC 8032 — enough to prove a tap's content came
from a trusted key (see :mod:`minisign`), and no more. Signing is intentionally
absent: boost verifies, publishers sign with real tools (``minisign``, Sigstore).

Correctness is pinned by the RFC 8032 §7.1 test vectors in the unit suite; if the
field math were wrong those known-good signatures would not verify. Speed is a
non-goal — a tap is verified once at ``tap`` time, not in a hot loop.
"""
from __future__ import annotations

import hashlib

# Curve25519 / edwards25519 constants (RFC 8032 §5.1).
_P = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493  # group order
_D = (-121665 * pow(121666, _P - 2, _P)) % _P
_I = pow(2, (_P - 1) // 4, _P)                            # sqrt(-1) mod p


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def _sha512_modl(data: bytes) -> int:
    return int.from_bytes(_sha512(data), "little") % _L


# Points are kept in extended homogeneous coordinates (X, Y, Z, T) with
# x = X/Z, y = Y/Z, x*y = T/Z — the standard trick that makes addition
# complete and branch-free.
def _point_add(p, q):
    px, py, pz, pt = p
    qx, qy, qz, qt = q
    a = ((py - px) * (qy - qx)) % _P
    b = ((py + px) * (qy + qx)) % _P
    c = (2 * pt * qt * _D) % _P
    dd = (2 * pz * qz) % _P
    e = b - a
    f = dd - c
    g = dd + c
    h = b + a
    return ((e * f) % _P, (h * g) % _P, (f * g) % _P, (e * h) % _P)


def _point_mul(scalar: int, point):
    result = (0, 1, 1, 0)  # neutral element
    while scalar > 0:
        if scalar & 1:
            result = _point_add(result, point)
        point = _point_add(point, point)
        scalar >>= 1
    return result


def _point_equal(p, q) -> bool:
    px, py, pz, _ = p
    qx, qy, qz, _ = q
    # x1/z1 == x2/z2  and  y1/z1 == y2/z2, cross-multiplied to avoid inverses.
    if (px * qz - qx * pz) % _P != 0:
        return False
    return (py * qz - qy * pz) % _P == 0


def _recover_x(y: int, sign: int):
    """The x matching a compressed y, or None if y is off the curve."""
    if y >= _P:
        return None
    xx = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P)
    x = pow(xx % _P, (_P + 3) // 8, _P)
    if (x * x - xx) % _P != 0:
        x = (x * _I) % _P
    if (x * x - xx) % _P != 0:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


# Base point B (RFC 8032 §5.1). Its y is on the curve by construction, so
# _recover_x always returns an int here; the guard makes that invariant explicit
# (and narrows the type) without an assert, which the SAST lint rules forbid.
_By = (4 * pow(5, _P - 2, _P)) % _P
_Bx = _recover_x(_By, 0)
if _Bx is None:  # pragma: no cover - unreachable: B is on the curve
    raise RuntimeError("edwards25519 base point is off the curve")
_B = (_Bx, _By, 1, (_Bx * _By) % _P)


def _point_decompress(data: bytes):
    """Decode a 32-byte compressed point, or None if it is not on the curve."""
    if len(data) != 32:
        return None
    y = int.from_bytes(data, "little")
    sign = (y >> 255) & 1
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, (x * y) % _P)


def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """True iff ``signature`` is a valid Ed25519 signature of ``message``.

    ``public_key`` is 32 bytes, ``signature`` 64. Any malformed input — wrong
    length, a point off the curve, a scalar ``S`` at or above the group order —
    returns False rather than raising, so a caller can treat a bad signature and
    a bad blob identically.
    """
    if len(public_key) != 32 or len(signature) != 64:
        return False
    a = _point_decompress(public_key)
    if a is None:
        return False
    r_bytes = signature[:32]
    r = _point_decompress(r_bytes)
    if r is None:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= _L:
        return False
    h = _sha512_modl(r_bytes + public_key + message)
    sb = _point_mul(s, _B)
    ha = _point_mul(h, a)
    return _point_equal(sb, _point_add(r, ha))
