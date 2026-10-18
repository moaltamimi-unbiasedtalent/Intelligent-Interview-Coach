"""Country profiles for Canada, Mexico and Brazil (GKB-8, GKB-9, GKB-10; PROPOSED ENGINEERING DESIGN). A profile states only what is NOT a data claim: the ISO country code, the national
occupation taxonomy scheme to be used, the national currency (an ISO 4217 fact) and the ISO 3166-2 subdivision vocabulary used to VALIDATE a region value. It records no source, no
taxonomy edition, no code format, no language and no occupation: those must come from actual source evidence at acquisition (owner decisions D-04, D-12, D-13). A region value that is not in
the vocabulary is rejected, never guessed, and a regional figure is never turned into a national one."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["CountryProfile", "PROFILES", "WIDER_SA_PROFILES", "normalize_region", "profile_for"]


@dataclass(frozen=True)
class CountryProfile:
    country: str
    name: str
    taxonomy_scheme: str
    currency: str
    region_kind: str
    regions: frozenset[str]          # ISO 3166-2 subdivision codes WITHOUT the country prefix
    enforce_currency: bool = True    # False: ``currency`` is only the ISO expectation and the SOURCE ROW must state its own currency (P10C-E wider South America)
    note: str = ""


_CA = "AB BC MB NB NL NS NT NU ON PE QC SK YT"
_MX = ("AGU BCN BCS CAM CHP CHH CMX COA COL DUR GUA GRO HID JAL MEX MIC MOR NAY NLE OAX PUE QUE ROO SLP SIN SON TAB TAM TLA VER YUC ZAC")
_BR = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO"

PROFILES: dict[str, CountryProfile] = {
    "CA": CountryProfile("CA", "Canada", "noc", "CAD", "province_or_territory", frozenset(_CA.split())),
    "MX": CountryProfile("MX", "Mexico", "sinco", "MXN", "state", frozenset(_MX.split())),
    "BR": CountryProfile("BR", "Brazil", "cbo", "BRL", "state_or_federal_district", frozenset(_BR.split())),
}


# Wider South America (GKB-11, P10C-E). National occupation classifications of these countries are NOT identified (their ISCO-08 based variants, if any, are unverified), so the only
# taxonomy namespace usable today is ISCO (international): the scheme is ``isco`` and the edition must still come from the source. The currency is only the ISO 4217 expectation; each source
# row must state its own (dollarised or multi-currency economies make a fixed expectation unsafe). The subdivision vocabularies are ISO 3166-2 reference lists to VALIDATE a region value.
# Paraguay and Peru are left EMPTY on purpose (vocabulary not yet recorded): a regional row for them is rejected until it is, never guessed.
_WIDER_SA = {
    "AR": ("Argentina", "ARS", "province_or_federal_district", "A B C D E F G H J K L M N P Q R S T U V W X Y Z"),
    "BO": ("Bolivia", "BOB", "department", "B C H L N O P S T"),
    "CL": ("Chile", "CLP", "region", "AI AN AP AR AT BI CO LI LL LR MA ML NB RM TA VS"),
    "CO": ("Colombia", "COP", "department_or_capital_district", "AMA ANT ARA ATL BOL BOY CAL CAQ CAS CAU CES CHO COR CUN DC GUA GUV HUI LAG MAG MET NAR NSA PUT QUI RIS SAP SAN SUC TOL VAC VAU VID"),
    "EC": ("Ecuador", "USD", "province", "A B C D E F G H I L M N O P R S SD SE T U W X Y Z"),
    "GY": ("Guyana", "GYD", "region", "BA CU DE EB ES MA PM PT UD UT"),
    "PY": ("Paraguay", "PYG", "department", ""),
    "PE": ("Peru", "PEN", "region", ""),
    "SR": ("Suriname", "SRD", "district", "BR CM CR MA NI PM PR SA SI WA"),
    "UY": ("Uruguay", "UYU", "department", "AR CA CL CO DU FD FS LA MA MO PA RN RO RV SA SJ SO TA TT"),
    "VE": ("Venezuela", "VES", "state_or_capital_district", "A B C D E F G H I J K L M N O P R S T U V W X Y Z"),
}
WIDER_SA_PROFILES: dict[str, CountryProfile] = {
    c: CountryProfile(c, name, "isco", cur, kind, frozenset(regs.split()), enforce_currency=False,
                      note="no national occupation classification identified: ISCO namespace only; edition, source, currency and region vocabulary must come from evidence" + ("; region vocabulary not yet recorded" if not regs else ""))
    for c, (name, cur, kind, regs) in _WIDER_SA.items()}


def profile_for(country: str | None) -> CountryProfile | None:
    c = (country or "").strip().upper()
    return PROFILES.get(c) or WIDER_SA_PROFILES.get(c)


def normalize_region(country: str | None, value: str | None) -> str | None:
    """``ON`` or ``CA-ON`` becomes ``CA-ON`` for a profiled country; anything outside the vocabulary (or a country without a profile) returns None. Case-insensitive; no fuzzy matching and no
    translation of names."""
    prof = profile_for(country)
    if prof is None or not value or not str(value).strip():
        return None
    v = str(value).strip().upper()
    if v.startswith(prof.country + "-"):
        v = v[len(prof.country) + 1:]
    return f"{prof.country}-{v}" if v in prof.regions else None
