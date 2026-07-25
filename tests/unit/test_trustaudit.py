"""Unit tests: boost_cli/core/trustaudit.py — the decision layer behind
`boost audit --skills`.

Every function is pure, so each branch, each severity mapping and each constant
literal is pinned here with assertions specific enough to kill mutants.
"""
from __future__ import annotations

from boost_cli.core import provenance, trustaudit


class TestConstants:
    def test_severity_literals(self):
        assert trustaudit.HIGH == "HIGH"
        assert trustaudit.MED == "MED"
        assert trustaudit.LOW == "LOW"

    def test_label_literals(self):
        assert trustaudit.INVALID_SIGNATURE == "invalid-signature"
        assert trustaudit.UNTRUSTED_TAP == "untrusted-tap"
        assert trustaudit.UNSIGNED_TAP == "unsigned-tap"
        assert trustaudit.LOCAL_SOURCE == "local-source"
        assert trustaudit.STALE_TAP == "stale-tap"
        assert trustaudit.BEHIND_TAP == "behind-tap"
        assert trustaudit.CONFLICT == "conflict"

    def test_stale_tap_days_default(self):
        assert trustaudit.STALE_TAP_DAYS == 30

    def test_only_invalid_signature_is_high(self):
        # A malformed signature is the one HIGH: the tap actively misrepresents
        # its provenance. Everything else is a decision or context.
        high = [lbl for lbl, sev in trustaudit.SEVERITY.items()
                if sev == trustaudit.HIGH]
        assert high == [trustaudit.INVALID_SIGNATURE]

    def test_untrusted_and_conflict_are_medium(self):
        assert trustaudit.SEVERITY[trustaudit.UNTRUSTED_TAP] == trustaudit.MED
        assert trustaudit.SEVERITY[trustaudit.CONFLICT] == trustaudit.MED

    def test_remaining_labels_are_low(self):
        for label in (trustaudit.UNSIGNED_TAP, trustaudit.LOCAL_SOURCE,
                      trustaudit.STALE_TAP, trustaudit.BEHIND_TAP):
            assert trustaudit.SEVERITY[label] == trustaudit.LOW

    def test_every_label_has_a_severity(self):
        labels = {trustaudit.INVALID_SIGNATURE, trustaudit.UNTRUSTED_TAP,
                  trustaudit.UNSIGNED_TAP, trustaudit.LOCAL_SOURCE,
                  trustaudit.STALE_TAP, trustaudit.BEHIND_TAP,
                  trustaudit.CONFLICT}
        assert set(trustaudit.SEVERITY) == labels


class TestSigningLabel:
    def test_verified_is_healthy(self):
        assert trustaudit.signing_label(provenance.VERIFIED) is None

    def test_invalid_signature(self):
        assert (trustaudit.signing_label(provenance.INVALID)
                == trustaudit.INVALID_SIGNATURE)

    def test_untrusted(self):
        assert (trustaudit.signing_label(provenance.UNTRUSTED)
                == trustaudit.UNTRUSTED_TAP)

    def test_unsigned(self):
        assert (trustaudit.signing_label(provenance.UNSIGNED)
                == trustaudit.UNSIGNED_TAP)

    def test_none_status_reads_as_unsigned(self):
        # tap recorded but its clone is gone: boost cannot show a signature it
        # cannot read, and must not silently pass.
        assert trustaudit.signing_label(None) == trustaudit.UNSIGNED_TAP

    def test_unrecognized_status_reads_as_unsigned(self):
        assert trustaudit.signing_label("weird") == trustaudit.UNSIGNED_TAP

    def test_local_wins_over_status(self):
        # is_local is checked FIRST — a path import has no tap, so even a
        # VERIFIED status (impossible in practice) must report local-source.
        assert (trustaudit.signing_label(provenance.VERIFIED, is_local=True)
                == trustaudit.LOCAL_SOURCE)
        assert (trustaudit.signing_label(None, is_local=True)
                == trustaudit.LOCAL_SOURCE)

    def test_is_local_defaults_to_false(self):
        assert trustaudit.signing_label(provenance.VERIFIED) is None


class TestStaleTapLabel:
    def test_none_age_is_no_signal(self):
        assert trustaudit.stale_tap_label(None) is None

    def test_older_than_limit_is_stale(self):
        assert (trustaudit.stale_tap_label(trustaudit.STALE_TAP_DAYS + 1)
                == trustaudit.STALE_TAP)

    def test_exactly_at_limit_is_fresh(self):
        # strictly greater-than: a tap synced exactly `limit` days ago is fresh
        assert trustaudit.stale_tap_label(trustaudit.STALE_TAP_DAYS) is None

    def test_younger_than_limit_is_fresh(self):
        assert trustaudit.stale_tap_label(0) is None

    def test_custom_limit_is_honored(self):
        assert trustaudit.stale_tap_label(5, limit=4) == trustaudit.STALE_TAP
        assert trustaudit.stale_tap_label(5, limit=5) is None


def _labels(findings):
    return [f["label"] for f in findings]


class TestSkillFindings:
    def test_fully_healthy_skill_has_no_findings(self):
        assert trustaudit.skill_findings(
            is_local=False, provenance_status=provenance.VERIFIED,
            tap_age_days=1, upstream_reason=None) == []

    def test_unsigned_tap_only(self):
        found = trustaudit.skill_findings(
            is_local=False, provenance_status=provenance.UNSIGNED,
            tap_age_days=0, upstream_reason=None)
        assert _labels(found) == [trustaudit.UNSIGNED_TAP]
        assert found[0]["severity"] == trustaudit.LOW
        assert found[0]["detail"] == "tap publishes no signature"

    def test_missing_clone_detail_differs_from_plain_unsigned(self):
        found = trustaudit.skill_findings(
            is_local=False, provenance_status=None,
            tap_age_days=None, upstream_reason=None)
        assert _labels(found) == [trustaudit.UNSIGNED_TAP]
        assert "tap clone is missing" in found[0]["detail"]

    def test_untrusted_detail(self):
        found = trustaudit.skill_findings(
            is_local=False, provenance_status=provenance.UNTRUSTED,
            tap_age_days=0, upstream_reason=None)
        assert "not in your trusted set" in found[0]["detail"]

    def test_invalid_detail(self):
        found = trustaudit.skill_findings(
            is_local=False, provenance_status=provenance.INVALID,
            tap_age_days=0, upstream_reason=None)
        assert found[0]["severity"] == trustaudit.HIGH
        assert "does not validate" in found[0]["detail"]

    def test_stale_tap_reports_the_age(self):
        found = trustaudit.skill_findings(
            is_local=False, provenance_status=provenance.VERIFIED,
            tap_age_days=99, upstream_reason=None)
        assert _labels(found) == [trustaudit.STALE_TAP]
        assert found[0]["detail"] == "tap last synced 99 days ago"

    def test_behind_tap_names_the_reason(self):
        found = trustaudit.skill_findings(
            is_local=False, provenance_status=provenance.VERIFIED,
            tap_age_days=0, upstream_reason="version")
        assert _labels(found) == [trustaudit.BEHIND_TAP]
        assert found[0]["detail"] == "tap has a newer copy (version)"

    def test_local_skill_reports_only_local_source(self):
        # a path import has no upstream, so tap-age and drift are not signals
        # about it — even when the caller passes them.
        found = trustaudit.skill_findings(
            is_local=True, provenance_status=None,
            tap_age_days=9999, upstream_reason="version")
        assert _labels(found) == [trustaudit.LOCAL_SOURCE]
        assert "no tap signature to check" in found[0]["detail"]

    def test_conflicts_are_reported_per_peer(self):
        found = trustaudit.skill_findings(
            is_local=False, provenance_status=provenance.VERIFIED,
            tap_age_days=0, upstream_reason=None,
            conflicts_with=("beta", "alpha"))
        assert _labels(found) == [trustaudit.CONFLICT, trustaudit.CONFLICT]
        details = sorted(f["detail"] for f in found)
        assert details == ["declares a conflict with alpha",
                           "declares a conflict with beta"]

    def test_conflicts_reported_for_a_local_skill_too(self):
        # a conflict is about the installed set, not about provenance, so it
        # must survive the is_local carve-out.
        found = trustaudit.skill_findings(
            is_local=True, provenance_status=None, tap_age_days=None,
            upstream_reason=None, conflicts_with=("peer",))
        assert _labels(found) == [trustaudit.CONFLICT, trustaudit.LOCAL_SOURCE]

    def test_worst_severity_sorts_first(self):
        found = trustaudit.skill_findings(
            is_local=False, provenance_status=provenance.INVALID,
            tap_age_days=99, upstream_reason="content",
            conflicts_with=("peer",))
        assert _labels(found) == [trustaudit.INVALID_SIGNATURE,  # HIGH
                                  trustaudit.CONFLICT,           # MED
                                  trustaudit.BEHIND_TAP,         # LOW
                                  trustaudit.STALE_TAP]          # LOW

    def test_stale_after_override(self):
        found = trustaudit.skill_findings(
            is_local=False, provenance_status=provenance.VERIFIED,
            tap_age_days=3, upstream_reason=None, stale_after=2)
        assert _labels(found) == [trustaudit.STALE_TAP]

    def test_conflicts_default_is_empty(self):
        assert trustaudit.skill_findings(
            is_local=False, provenance_status=provenance.VERIFIED,
            tap_age_days=0, upstream_reason=None) == []


class TestSortFindings:
    def _f(self, severity, label, detail="d"):
        return {"severity": severity, "label": label, "detail": detail}

    def test_severity_rank_beats_label_order(self):
        rows = [self._f(trustaudit.LOW, "aaa"), self._f(trustaudit.HIGH, "zzz")]
        assert _labels(trustaudit.sort_findings(rows)) == ["zzz", "aaa"]

    def test_med_sorts_between_high_and_low(self):
        rows = [self._f(trustaudit.LOW, "l"), self._f(trustaudit.HIGH, "h"),
                self._f(trustaudit.MED, "m")]
        assert _labels(trustaudit.sort_findings(rows)) == ["h", "m", "l"]

    def test_label_breaks_severity_ties(self):
        rows = [self._f(trustaudit.LOW, "b"), self._f(trustaudit.LOW, "a")]
        assert _labels(trustaudit.sort_findings(rows)) == ["a", "b"]

    def test_detail_breaks_label_ties(self):
        rows = [self._f(trustaudit.LOW, "x", "z"), self._f(trustaudit.LOW, "x", "a")]
        assert [f["detail"] for f in trustaudit.sort_findings(rows)] == ["a", "z"]

    def test_does_not_mutate_the_input(self):
        rows = [self._f(trustaudit.LOW, "b"), self._f(trustaudit.HIGH, "a")]
        trustaudit.sort_findings(rows)
        assert _labels(rows) == ["b", "a"]


class TestCountSeverities:
    def test_empty(self):
        assert trustaudit.count_severities({}) == {
            trustaudit.HIGH: 0, trustaudit.MED: 0, trustaudit.LOW: 0}

    def test_counts_across_skills(self):
        by_skill = {
            "a": [{"severity": trustaudit.HIGH, "label": "x", "detail": "d"},
                  {"severity": trustaudit.LOW, "label": "y", "detail": "d"}],
            "b": [{"severity": trustaudit.LOW, "label": "z", "detail": "d"}],
        }
        assert trustaudit.count_severities(by_skill) == {
            trustaudit.HIGH: 1, trustaudit.MED: 0, trustaudit.LOW: 2}

    def test_a_skill_with_no_findings_contributes_nothing(self):
        assert trustaudit.count_severities({"a": []}) == {
            trustaudit.HIGH: 0, trustaudit.MED: 0, trustaudit.LOW: 0}


class TestVerdict:
    def test_clean_is_healthy(self):
        assert trustaudit.is_healthy(
            {trustaudit.HIGH: 0, trustaudit.MED: 0, trustaudit.LOW: 0}) is True

    def test_low_only_stays_healthy(self):
        # an unsigned tap is the norm for most of the catalog — treating it as
        # unhealthy would make the command cry wolf on an ordinary install.
        assert trustaudit.is_healthy(
            {trustaudit.HIGH: 0, trustaudit.MED: 0, trustaudit.LOW: 7}) is True

    def test_high_is_unhealthy(self):
        assert trustaudit.is_healthy(
            {trustaudit.HIGH: 1, trustaudit.MED: 0, trustaudit.LOW: 0}) is False

    def test_med_is_unhealthy(self):
        assert trustaudit.is_healthy(
            {trustaudit.HIGH: 0, trustaudit.MED: 1, trustaudit.LOW: 0}) is False

    def test_exit_code_matches_health(self):
        assert trustaudit.exit_code(
            {trustaudit.HIGH: 0, trustaudit.MED: 0, trustaudit.LOW: 3}) == 0
        assert trustaudit.exit_code(
            {trustaudit.HIGH: 0, trustaudit.MED: 2, trustaudit.LOW: 0}) == 1
        assert trustaudit.exit_code(
            {trustaudit.HIGH: 1, trustaudit.MED: 0, trustaudit.LOW: 0}) == 1


class TestRelationList:
    def test_none_meta(self):
        assert trustaudit.relation_list(None, "conflicts") == []

    def test_missing_key(self):
        assert trustaudit.relation_list({}, "conflicts") == []

    def test_empty_string_value(self):
        assert trustaudit.relation_list({"conflicts": ""}, "conflicts") == []

    def test_false_value(self):
        assert trustaudit.relation_list({"conflicts": False}, "conflicts") == []

    def test_none_value(self):
        assert trustaudit.relation_list({"conflicts": None}, "conflicts") == []

    def test_list_value_is_stripped(self):
        assert trustaudit.relation_list(
            {"conflicts": [" a ", "b"]}, "conflicts") == ["a", "b"]

    def test_list_value_drops_blanks(self):
        assert trustaudit.relation_list(
            {"conflicts": ["a", "", "   "]}, "conflicts") == ["a"]

    def test_comma_string_is_split(self):
        assert trustaudit.relation_list(
            {"conflicts": "a, b ,c"}, "conflicts") == ["a", "b", "c"]

    def test_comma_string_drops_blanks(self):
        assert trustaudit.relation_list(
            {"conflicts": "a,,b,"}, "conflicts") == ["a", "b"]

    def test_single_name_string(self):
        assert trustaudit.relation_list({"conflicts": "solo"}, "conflicts") == ["solo"]

    def test_reads_the_requested_key_only(self):
        meta = {"requires": ["r"], "conflicts": ["c"]}
        assert trustaudit.relation_list(meta, "requires") == ["r"]
        assert trustaudit.relation_list(meta, "conflicts") == ["c"]

    def test_non_string_list_items_are_coerced(self):
        assert trustaudit.relation_list({"conflicts": [7]}, "conflicts") == ["7"]


class TestConflictPairs:
    def test_no_conflicts(self):
        assert trustaudit.conflict_pairs(["a", "b"], lambda n: []) == []

    def test_peer_not_installed_is_dropped(self):
        pairs = trustaudit.conflict_pairs(
            ["a"], lambda n: ["ghost"] if n == "a" else [])
        assert pairs == []

    def test_self_conflict_is_dropped(self):
        assert trustaudit.conflict_pairs(["a"], lambda n: ["a"]) == []

    def test_blank_peer_is_dropped(self):
        assert trustaudit.conflict_pairs(["a", "b"], lambda n: [""]) == []

    def test_one_sided_conflict(self):
        pairs = trustaudit.conflict_pairs(
            ["a", "b"], lambda n: ["b"] if n == "a" else [])
        assert pairs == [("a", "b")]

    def test_mutual_conflict_reported_from_both_sides(self):
        # both skills are equally implicated, so both get a finding
        table = {"a": ["b"], "b": ["a"]}
        pairs = trustaudit.conflict_pairs(["a", "b"], lambda n: table.get(n, []))
        assert pairs == [("a", "b"), ("b", "a")]

    def test_duplicate_declarations_are_deduped(self):
        pairs = trustaudit.conflict_pairs(
            ["a", "b"], lambda n: ["b", "b"] if n == "a" else [])
        assert pairs == [("a", "b")]

    def test_result_is_sorted(self):
        table = {"c": ["a"], "b": ["a"]}
        pairs = trustaudit.conflict_pairs(["a", "b", "c"],
                                          lambda n: table.get(n, []))
        assert pairs == [("b", "a"), ("c", "a")]

    def test_duplicate_installed_names_do_not_duplicate_pairs(self):
        pairs = trustaudit.conflict_pairs(
            ["a", "a", "b"], lambda n: ["b"] if n == "a" else [])
        assert pairs == [("a", "b")]
