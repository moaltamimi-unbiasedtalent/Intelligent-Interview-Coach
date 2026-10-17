"""Exact money (GKB-5). Amounts are ``Decimal`` in the domain and exact SCALED INTEGERS in the database: no floating point is ever stored. Float input is REJECTED (a value must arrive
as an int, a string or a Decimal; adapters convert a parsed source number through its shortest decimal text, which is exact for published figures). A value is never rounded: more than
six decimal places is an error, not a silent truncation. Zero and negative amounts are not valid reported compensation (a missing value is expressed as an explicit status, never as 0).
Currencies are ISO 4217 codes; nothing here converts between currencies or pay periods."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

__all__ = ["MoneyError", "ISO_4217", "validate_currency", "to_units", "from_units", "scale_of", "MAX_SCALE"]

MAX_SCALE = 6
ISO_4217 = frozenset("""AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BRL BSD BTN BWP BYN BZD CAD CDF CHF CLP CNY COP CRC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB
EUR FJD FKP GBP GEL GHS GIP GMD GNF GTQ GYD HKD HNL HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA MKD MMK MNT MOP MRU
MUR MVR MWK MXN MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY
TTD TWD TZS UAH UGX USD UYU UZS VED VES VND VUV WST XAF XCD XOF XPF YER ZAR ZMW ZWL""".split())


class MoneyError(ValueError):
    """An amount or currency was invalid. Messages never contain source content."""


def validate_currency(code: str | None) -> str:
    c = (code or "").strip()
    if len(c) != 3 or not c.isalpha() or c != c.upper() or c not in ISO_4217:
        raise MoneyError("invalid ISO 4217 currency code")
    return c


def _decimal(value) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise MoneyError("a float is not an accepted money input (use a string, int or Decimal)")
    try:
        d = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise MoneyError("malformed amount") from exc
    if not d.is_finite():
        raise MoneyError("amount must be finite")
    return d


def scale_of(value) -> int:
    d = _decimal(value)
    exp = d.normalize().as_tuple().exponent
    scale = max(0, -int(exp))
    if scale > MAX_SCALE:
        raise MoneyError("more than six decimal places: refusing to round")
    return scale


def to_units(value, scale: int) -> int:
    """Exact integer units of ``value`` at ``scale`` decimal places. Refuses a non-positive amount and any value that does not fit the scale without rounding."""
    d = _decimal(value)
    if d <= 0:
        raise MoneyError("a reported amount must be positive")
    if not 0 <= scale <= MAX_SCALE:
        raise MoneyError("invalid scale")
    scaled = d.scaleb(scale)
    if scaled != scaled.to_integral_value():
        raise MoneyError("value does not fit the scale without rounding")
    return int(scaled)


def from_units(units: int | None, scale: int) -> Decimal | None:
    if units is None:
        return None
    return Decimal(int(units)).scaleb(-scale)
