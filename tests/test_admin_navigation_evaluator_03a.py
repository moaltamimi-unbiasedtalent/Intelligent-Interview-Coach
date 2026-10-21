"""03A: the Admin foundation evaluator counts destinations from the ADMIN_DESTINATIONS array only and checks the six navigation groups separately.
The legitimate structure passes; an extra unauthorised destination, a misplaced or duplicated destination, a seventh group and permission logic inside a group are rejected."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import tests.conftest  # noqa: F401  (isolation first)

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("eval_admin_foundation", ROOT / "scripts/eval_admin_foundation.py")
EV = importlib.util.module_from_spec(spec)
spec.loader.exec_module(EV)

CAPS = (ROOT / "frontend/lib/admin/capabilities.ts").read_text(encoding="utf-8")


def test_the_real_navigation_structure_is_twenty_destinations_in_six_groups():
    assert len(EV.destination_ids(CAPS)) == 20 and len(set(EV.destination_ids(CAPS))) == 20
    assert EV.navigation_group_problems(CAPS) == []
    results = EV.run()
    assert results["only_operational_destinations_listed"][0] and results["navigation_groups_are_six_and_place_each_destination_once"][0]


def test_group_identifiers_are_not_counted_as_destinations():
    ids = EV.destination_ids(CAPS)
    assert len(ids) == 20 and not {"command", "customers", "commercial", "insights", "governance"} & set(ids)      # ("ai" is a destination AND a group id: separate namespaces)
    assert "ADMIN_GROUPS" not in EV.destinations_block(CAPS)


def test_an_extra_unauthorised_destination_is_rejected():
    extra = CAPS.replace('export const ADMIN_DESTINATIONS: readonly AdminDestination[] = [\n',
                         'export const ADMIN_DESTINATIONS: readonly AdminDestination[] = [\n  { id: "rogue", label: "Rogue", href: "/admin/rogue", description: "x", anyOf: [] },\n', 1)
    assert len(EV.destination_ids(extra)) == 21                                  # the count check (== 20) now fails
    assert any("rogue" in p for p in EV.navigation_group_problems(extra))        # and the placement check reports it as unplaced


def test_a_planned_destination_label_is_still_detected():
    planned = CAPS.replace('label: "Billing"', 'label: "Subscriptions"', 1)
    assert 'label: "Subscriptions' in EV.destinations_block(planned)


def test_incorrect_grouping_is_rejected():
    duplicated = CAPS.replace('destinationIds: ["overview"]', 'destinationIds: ["overview", "users"]', 1)
    assert any("more than one group" in p for p in EV.navigation_group_problems(duplicated))
    missing = CAPS.replace('"users", "workspaces", "support", "privacy"', '"workspaces", "support", "privacy"', 1)
    assert any("missing ['users']" in p for p in EV.navigation_group_problems(missing))
    unknown = CAPS.replace('["plans", "billing"]', '["plans", "billing", "ghost"]', 1)
    assert any("unknown ['ghost']" in p for p in EV.navigation_group_problems(unknown))


def test_a_seventh_group_or_permission_logic_in_a_group_is_rejected():
    seventh = CAPS.replace(' { id: "governance",', ' { id: "extra", label: "Extra", destinationIds: [] },\n  { id: "governance",', 1)
    assert any("exactly 6" in p for p in EV.navigation_group_problems(seventh))
    gated = CAPS.replace('{ id: "command", label: "Command Center", destinationIds: ["overview"] }', '{ id: "command", label: "Command Center", destinationIds: ["overview"], anyOf: [] }', 1)
    assert any("permission logic" in p for p in EV.navigation_group_problems(gated))
    bypass = CAPS.replace("const visible = visibleDestinations(granted);", "const visible = ADMIN_DESTINATIONS.slice();", 1)
    assert any("permission-filtered" in p for p in EV.navigation_group_problems(bypass))
