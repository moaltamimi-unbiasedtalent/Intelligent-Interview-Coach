# P10D product-coverage root causes [developer_local]

386/412 sufficient (gate needs 392): BELOW_GATE.

- 8 x outlook: the occupation is not mapped to a BLS-projections occupation; no mapping is forced
- 7 x compensation (US): no official record matches this occupation title in the runtime store; no mapping is forced (a P10C resolver and source-qualification dependency)
- 7 x compensation (UK): no official record matches this occupation title in the runtime store; no mapping is forced (a P10C resolver and source-qualification dependency)
- 4 x education: the resolved occupation has no education attribute (BLS OOH covers a subset of occupations)

Sufficient only because of synthetic-fixture evidence: ['pc_certifications_110', 'pc_certifications_120', 'pc_licences_130']. Excluding them: 383/412.
