"""Per-language AI behaviour evidence tooling (package 06C: LG-04 and LG-05, engineering part).

Offline and deterministic: nothing here calls a model, a provider or the network, and nothing here approves a language. The modules are

* ``inventory``  - every localized policy / safety / fallback sentence per language and the mechanical checks that find a missing or English-leaking one;
* ``invariance`` - the scoring-invariance report and its documented tolerance;
* ``rating``     - the blinded native-reader rating PROTOCOL and HARNESS (sampling plan, anonymised packets, rating sheets, aggregation).
"""

__all__: list[str] = []
