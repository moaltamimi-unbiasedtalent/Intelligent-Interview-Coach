"""Country profiles for Canada, Mexico and Brazil (GKB-8, GKB-9, GKB-10; PROPOSED ENGINEERING DESIGN). A profile states only what is NOT a data claim: the ISO country code, the national
occupation taxonomy scheme to be used, the national currency (an ISO 4217 fact) and the ISO 3166-2 subdivision vocabulary used to VALIDATE a region value. It records no source, no
taxonomy edition, no code format, no language and no occupation: those must come from actual source evidence at acquisition (owner decisions D-04, D-12, D-13). A region value that is not in
the vocabulary is rejected, never guessed, and a regional figure is never turned into a national one."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["CountryProfile", "PROFILES", "normalize_region", "profile_for"]


@dataclass(frozen=True)
class CountryProfile:
    country: str
    name: str
    taxonomy_scheme: str
    currency: str
    region_kind: str
    regions: frozenset[str]          # ISO 3166-2 subdivision codes WITHOUT the country prefix


_CA = "AB BC MB NB NL NS NT NU ON PE QC SK YT"
_MX = ("AGU BCN BCS CAM CHP CHH CMX COA COL DUR GUA GRO HID JAL MEX MIC MOR NAY NLE OAX PUE QUE ROO SLP SIN SON TAB TAM TLA VER YUC ZAC")
_BR = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO"

PROFILES: dict[str, CountryProfile] = {
    "CA": CountryProfile("CA", "Canada", "noc", "CAD", "province_or_territory", frozenset(_CA.split())),
    "MX": CountryProfile("MX", "Mexico", "sinco", "MXN", "state", frozenset(_MX.split())),
    "BR": CountryProfile("BR", "Brazil", "cbo", "BRL", "state_or_federal_district", frozenset(_BR.split())),
}


def profile_for(country: str | None) -> CountryProfile | None:
    return PROFILES.get((country or "").strip().upper())


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
