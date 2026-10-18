# P10C-F1 Acquisition Packages

*Generated from the dossier. Seven independently approvable packages; none is approved and no data has been downloaded.*

## Package 1: US: SOC 2018 + OEWS + mappings

- **Sources:** us_soc_2018, us_bls_oews, us_onet_db
- **Why needed:** Occupation-linked US compensation V2 evidence (the 1,386 V1 BLS records become SOC-linked evidence) and US wiring cases.
- **Capability:** Registry-gated import of the listed sources, only after owner approval of ingestion; no runtime use implied.
- **Licensing status:** {"us_soc_2018": "clear", "us_bls_oews": "clear", "us_onet_db": "clear"}
- **Acquisition requirements:** owner approval of ingestion for each listed source (D-04); manual download by owner or approved operator; record URL, edition, timestamp and SHA-256; registry-gated importer in production mode; synthetic fixtures never
- **Engineering dependencies:** ESCO nodes; ESCO or O*NET-SOC crosswalk to link resolver identities; SOC 2018 nodes; SOC 2018 nodes in the graph; approval of the SOC source; crosswalk to the resolver identities (ESCO, ISCO); measurement qualification by a named reviewer; owner confirmation of the attribution text; runtime approval of the source
- **Qualification tests:** edition and reference period match the dossier; occupation codes validate against the approved taxonomy edition; no value is scaled, annualised or currency-converted outside the source's own derivation; suppressed or missing cells stay missing; C-class matches the dossier proposal
- **Owner approval needed:** D-04 ingestion approval per source, D-12 edition selection, D-13 taxonomy acquisition
- **Legal review sources:** none identified
- **Ready for owner consideration:** True (not approved)
- **Limitations:**
  - An official SOC to ISCO-08 crosswalk was NOT found: its existence is NOT VERIFIED.
  - Annual rates are calculated from hourly rates using a typical 2,080-hour work year for hourly-reported occupations: this derivation is the PUBLISHER's, not a conversion by Ask4Mo, and must be labelled.
  - Published crosswalks on the page read: 2010 SOC to 2018 SOC (BLS XLSX with an explanatory note) and a CIP to 2018 SOC link (NCES). No crosswalk to ISCO-08 or O*NET-SOC is published on the pages read.
  - The ESCO-to-O*NET-SOC file does not state which ESCO edition it maps; mapping quality (exact, approximate, one-to-many) must be read from the file itself after acquisition (NOT VERIFIED).
  - Wages are straight-time GROSS pay exclusive of premium pay; included: base rates, cost-of-living allowances, guaranteed pay, hazardous-duty pay, incentive pay, tips; excluded: overtime, severance, shift differentials, nonproduction bonuses, employer-paid benefits (May 2024 notes).

## Package 2: UK: SOC 2020 + ASHE + mappings

- **Sources:** uk_soc_2020, uk_ons_ashe
- **Why needed:** Occupation-linked UK evidence for the 527 V1 ASHE rows (the one row without a code is rejected, never guessed) and UK wiring cases.
- **Capability:** Registry-gated import of the listed sources, only after owner approval of ingestion; no runtime use implied.
- **Licensing status:** {"uk_soc_2020": "clear", "uk_ons_ashe": "clear"}
- **Acquisition requirements:** owner approval of ingestion for each listed source (D-04); manual download by owner or approved operator; record URL, edition, timestamp and SHA-256; registry-gated importer in production mode; synthetic fixtures never
- **Engineering dependencies:** UK SOC 2020 nodes; a crosswalk to the resolver identities (ISCO-08 or ESCO); measurement qualification; owner adoption of UK SOC 2020 as first-class (D-03); runtime approval
- **Qualification tests:** edition and reference period match the dossier; occupation codes validate against the approved taxonomy edition; no value is scaled, annualised or currency-converted outside the source's own derivation; suppressed or missing cells stay missing; C-class matches the dossier proposal
- **Owner approval needed:** D-04 ingestion approval per source, D-12 edition selection, D-13 taxonomy acquisition, D-03
- **Legal review sources:** none identified
- **Ready for owner consideration:** True (not approved)
- **Limitations:**
  - A separate older ONS dataset maps ISCO-08 to UK SOC 2000 and 2010 (not SOC 2020).
  - Medians are the preferred measure; the headline weekly measure is gross weekly earnings for full-time employees (above 30 paid hours; 25 or more for teaching).
  - ONS publishes a page on classifying SOC 2020 to ISCO-08 and states the full coding index of about 30,000 job titles was recoded to ISCO-08 with the CASCOT tool; the index (Excel) includes ISCO-08 codes and an ISCO-08 structure worksheet (search summary of official pages). A mapping derived from a TITLE index is many-to-many and is not a unit-group equivalence: it would be PARTIAL or AMBIGUOUS, never VERIFIED equivalent.
  - Weekly and hourly figures cover employees whose pay for the survey period was not affected by absence; annual figures cover adult-rate employees in the same job for more than one year.

## Package 3: ESCO / ISCO / multilingual labels

- **Sources:** eu_esco, intl_isco08
- **Why needed:** Multilingual alias and identity base and the ISCO bridge for resolver identities.
- **Capability:** Registry-gated import of the listed sources, only after owner approval of ingestion; no runtime use implied.
- **Licensing status:** {"eu_esco": "unclear", "intl_isco08": "unclear"}
- **Acquisition requirements:** owner approval of ingestion for each listed source (D-04); manual download by owner or approved operator; record URL, edition, timestamp and SHA-256; registry-gated importer in production mode; synthetic fixtures never
- **Engineering dependencies:** ILO permission or legal confirmation; language approval (D-07); legal confirmation of the reuse basis
- **Qualification tests:** edition and reference period match the dossier; occupation codes validate against the approved taxonomy edition; no value is scaled, annualised or currency-converted outside the source's own derivation; suppressed or missing cells stay missing; C-class matches the dossier proposal
- **Owner approval needed:** D-04 ingestion approval per source, D-12 edition selection, D-13 taxonomy acquisition, D-07
- **Legal review sources:** eu_esco, intl_isco08
- **Ready for owner consideration:** False (not approved)
- **Limitations:**
  - Russian is not stated among languages on the pages read; the language list was summarised as 'Bulgarian through Norwegian Bokmål and Ukrainian' (full list at the ESCO languages page, not read): Russian availability is NOT VERIFIED.
  - The ILO landing page content was NOT read (redirect not followed); the licence finding rests on the ILO catalogue entry and the ILO rights page found by search.
  - The download page states the dataset is available in all 28 ESCO languages: multilingual availability is VERIFIED, but acquisition per language is not approved (D-07).

## Package 4: Germany / Eurostat

- **Sources:** eu_eurostat_ses, de_ba_entgeltatlas, de_destatis_genesis
- **Why needed:** Harmonised major-group earnings and German national evidence.
- **Capability:** Registry-gated import of the listed sources, only after owner approval of ingestion; no runtime use implied.
- **Licensing status:** {"eu_eurostat_ses": "clear", "de_ba_entgeltatlas": "not_verified", "de_destatis_genesis": "unclear"}
- **Acquisition requirements:** owner approval of ingestion for each listed source (D-04); manual download by owner or approved operator; record URL, edition, timestamp and SHA-256; registry-gated importer in production mode; synthetic fixtures never
- **Engineering dependencies:** BA permission or published terms; ISCO-08 nodes (and the ISCO legal review); classification and crosswalk; measurement qualification; runtime approval; table identification
- **Qualification tests:** edition and reference period match the dossier; occupation codes validate against the approved taxonomy edition; no value is scaled, annualised or currency-converted outside the source's own derivation; suppressed or missing cells stay missing; C-class matches the dossier proposal
- **Owner approval needed:** D-04 ingestion approval per source, D-12 edition selection, D-13 taxonomy acquisition
- **Legal review sources:** de_ba_entgeltatlas, de_destatis_genesis
- **Ready for owner consideration:** False (not approved)
- **Limitations:**
  - Measures: means (annual, monthly, hourly gross earnings); hourly earnings include overtime and paid non-working time; medians and deciles are not mentioned on the page read; units EUR, PPS, percentages and persons.
  - Occupation is published only at the ISCO-08 MAJOR GROUP: Eurostat does NOT provide occupation-specific compensation at unit-group level for any EU country in the online tables; any EU-wide or country-wide coverage claim for occupation-level pay is unsupported.
  - Secondary sources describe median monthly gross pay of full-time employees from pension-insurance contribution notifications; NOT confirmed from an official BA page.
  - The German K1 governed set (7 occupations, EUR gross annual, 2024) is a self-declared ENGINEERING DRAFT and is not Entgeltatlas data.
  - Which table, occupation classification and population would serve compensation was not established.

## Package 5: Canada

- **Sources:** ca_noc_2021, ca_jobbank_statcan
- **Why needed:** Canadian taxonomy and wage evidence.
- **Capability:** Registry-gated import of the listed sources, only after owner approval of ingestion; no runtime use implied.
- **Licensing status:** {"ca_noc_2021": "unclear", "ca_jobbank_statcan": "not_verified"}
- **Acquisition requirements:** owner approval of ingestion for each listed source (D-04); manual download by owner or approved operator; record URL, edition, timestamp and SHA-256; registry-gated importer in production mode; synthetic fixtures never
- **Engineering dependencies:** NOC nodes; crosswalk to the resolver identities (none published); dataset identification
- **Qualification tests:** edition and reference period match the dossier; occupation codes validate against the approved taxonomy edition; no value is scaled, annualised or currency-converted outside the source's own derivation; suppressed or missing cells stay missing; C-class matches the dossier proposal
- **Owner approval needed:** D-04 ingestion approval per source, D-12 edition selection, D-13 taxonomy acquisition
- **Legal review sources:** ca_jobbank_statcan
- **Ready for owner consideration:** False (not approved)
- **Limitations:**
  - Job Bank wages are derived from the Labour Force Survey (concept: hourly wage of employees) per secondary knowledge; NOT confirmed from an official page in this wave.
  - StatCan states a NOC to ISCO-08 concordance is planned but NOT published: no official NOC-ISCO crosswalk exists to import; none may be derived from titles.
  - Wage statistics at NOC unit-group level may be suppressed for small cells.

## Package 6: Mexico + Brazil

- **Sources:** mx_sinco_inegi, br_cbo_ibge
- **Why needed:** Mexican and Brazilian taxonomies and qualified earnings evidence.
- **Capability:** Registry-gated import of the listed sources, only after owner approval of ingestion; no runtime use implied.
- **Licensing status:** {"mx_sinco_inegi": "clear", "br_cbo_ibge": "not_verified"}
- **Acquisition requirements:** owner approval of ingestion for each listed source (D-04); manual download by owner or approved operator; record URL, edition, timestamp and SHA-256; registry-gated importer in production mode; synthetic fixtures never
- **Engineering dependencies:** BR adapter; CBO nodes; SINCO nodes; concept qualification; country adapter for MX; earnings-concept qualification
- **Qualification tests:** edition and reference period match the dossier; occupation codes validate against the approved taxonomy edition; no value is scaled, annualised or currency-converted outside the source's own derivation; suppressed or missing cells stay missing; C-class matches the dossier proposal
- **Owner approval needed:** D-04 ingestion approval per source, D-12 edition selection, D-13 taxonomy acquisition
- **Legal review sources:** br_cbo_ibge
- **Ready for owner consideration:** False (not approved)
- **Limitations:**
  - ENOE is a household labour survey: household or total income must NEVER be recorded as occupational compensation; only an earnings variable defined for employed persons by occupation, if published, can qualify.
  - Household income is not occupational compensation.
  - No official SINCO to ISCO-08 crosswalk was identified (NOT VERIFIED).
  - PNAD Continua is a household SURVEY; RAIS/eSocial administrative records are a different evidence type: survey evidence must not be labelled administrative.

## Package 7: Wider South America + ILOSTAT

- **Sources:** sa_ar, sa_bo, sa_cl, sa_co, sa_ec, sa_gy, sa_py, sa_pe, sa_sr, sa_uy, sa_ve, intl_ilostat
- **Why needed:** Wider South American markets and the harmonised international contract.
- **Capability:** Registry-gated import of the listed sources, only after owner approval of ingestion; no runtime use implied.
- **Licensing status:** {"sa_ar": "not_verified", "sa_bo": "not_verified", "sa_cl": "clear", "sa_co": "not_verified", "sa_ec": "not_verified", "sa_gy": "not_verified", "sa_py": "not_verified", "sa_pe": "not_verified", "sa_sr": "not_verified", "sa_uy": "not_verified", "sa_ve": "not_verified", "intl_ilostat": "unclear"}
- **Acquisition requirements:** owner approval of ingestion for each listed source (D-04); manual download by owner or approved operator; record URL, edition, timestamp and SHA-256; registry-gated importer in production mode; synthetic fixtures never
- **Engineering dependencies:** D-16; ISCO nodes
- **Qualification tests:** edition and reference period match the dossier; occupation codes validate against the approved taxonomy edition; no value is scaled, annualised or currency-converted outside the source's own derivation; suppressed or missing cells stay missing; C-class matches the dossier proposal
- **Owner approval needed:** D-04 ingestion approval per source, D-12 edition selection, D-13 taxonomy acquisition, D-16
- **Legal review sources:** sa_ar, sa_bo, sa_cl, sa_co, sa_ec, sa_gy, sa_py, sa_pe, sa_sr, sa_uy, sa_ve, intl_ilostat
- **Ready for owner consideration:** False (not approved)
- **Limitations:**
  - Household survey income must not be treated as compensation.
  - Occupational classification and earnings concept not verified from official pages.
  - Precedence category for non-Eurostat international harmonised sources is an OPEN owner decision (D-16): C3 must NOT be auto-assigned.
  - Values are harmonised by the ILO from national sources; concepts and populations vary by country and year.
