"""Antibody benchmark tests — CDR-H3 extraction, flag vocabulary, hard-fail gates.

Network-free: extraction is checked against offline PDB-derived fixtures.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestCDRH3Extraction:
    def test_reference_antibodies_match_published_cdrh3(self):
        from biochat.eval.antibody_benchmark import verify_extractor

        assert verify_extractor() == []

    def test_every_reference_has_an_offline_fixture(self):
        from biochat.eval.antibody_benchmark import _REFERENCE_CHAINS, EXTRACTION_REFERENCES

        for name, (entity, _) in EXTRACTION_REFERENCES.items():
            assert entity in _REFERENCE_CHAINS, f"{name}: missing fixture for {entity}"

    def test_light_chain_yields_no_cdrh3(self):
        from biochat.eval.antibody_benchmark import extract_cdrh3

        light = (
            "DIQMTQSPSSLSASVGDRVTITCRASQDVNTAVAWYQQKPGKAPKLLIYSASFLYSGVPSRFSGSRSGTDFTLTIS"
            "SLQPEDFATYYCQQHYTTPPTFGQGTKVEIK"
        )
        assert extract_cdrh3(light) is None

    def test_returns_none_without_fr4_motif(self):
        from biochat.eval.antibody_benchmark import extract_cdrh3

        assert extract_cdrh3("EVQLVESGGGLVQPGGSLRLSCAAS") is None
        assert extract_cdrh3("") is None
        assert extract_cdrh3(None) is None

    def test_span_is_consistent_with_extracted_sequence(self):
        from biochat.eval.antibody_benchmark import _REFERENCE_CHAINS, extract_cdrh3, extraction_span

        chain = _REFERENCE_CHAINS["1N8Z_2"]
        start, end = extraction_span(chain)
        assert chain[start:end] == extract_cdrh3(chain)


class TestFlagVocabulary:
    """Every flag generation_filter can emit must resolve in PENALTY_TABLE.

    A missing key silently degrades to ``("WARNING", 2, flag)``, which is how
    all four hard-exclusion conditions were once defeated.
    """

    def test_all_emitted_flags_are_in_the_penalty_table(self):
        from biochat.tool.antibody_design.schemas import PENALTY_TABLE

        source = (ROOT / "biochat/tool/antibody_design/generation_filter.py").read_text()
        static = set(re.findall(r'flags\.append\(\s*"([^"]+)"', source))
        dynamic = {f"high_single_{aa}_fraction" for aa in "FWY"}

        missing = sorted((static | dynamic) - set(PENALTY_TABLE))
        assert not missing, f"flags emitted but not in PENALTY_TABLE: {missing}"

    def test_filter_hard_fail_flags_are_hard_exclude(self):
        from biochat.tool.antibody_design.schemas import FILTER_HARD_FAIL_FLAGS, PENALTY_TABLE

        for flag in FILTER_HARD_FAIL_FLAGS:
            assert PENALTY_TABLE[flag][0] == "HARD_EXCLUDE", flag


class TestHardFailGate:
    """A candidate the filter rejects must never be scored as accepted."""

    HARD_FAILS = [
        ("AAANCSAAAKQ", "N-glycosylation motif"),
        ("CLFRNERYSYA", "extra cysteine"),
        ("AA", "below the allowed length"),
        ("A" * 40, "above the allowed length"),
    ]

    def test_filter_and_scorer_agree(self):
        from biochat.tool.antibody_design.generation_filter import filter_cdrh3_design
        from biochat.tool.antibody_design.scoring import score_candidate

        for seq, reason in self.HARD_FAILS:
            accepted, flags, metrics = filter_cdrh3_design(seq, "")
            scored = score_candidate(seq, "", "", flags, metrics)
            assert not accepted, f"{seq} ({reason}) should fail the filter"
            assert not scored["accepted"], f"{seq} ({reason}) scored as accepted"
            assert scored["aggregate_score"] == 0.0, f"{seq} ({reason}) scored {scored['aggregate_score']}"

    def test_production_api_never_promotes_a_hard_fail(self):
        from biochat.tool.antibody_design.api import score_and_rank_candidates

        sequences = [seq for seq, _ in self.HARD_FAILS] + ["WGGDGFYAMDY"]
        result = score_and_rank_candidates(sequences, "LHCPALVTYNT")

        promoted = {c["cdrh3_sequence"] for c in result["candidates"] if c["accepted"]}
        for seq, reason in self.HARD_FAILS:
            assert seq not in promoted, f"{seq} ({reason}) was promoted by the production API"

    def test_approved_antibody_still_passes(self):
        from biochat.tool.antibody_design.generation_filter import filter_cdrh3_design

        # Trastuzumab's CDR-H3 — an approved drug must not be hard-excluded.
        accepted, _, _ = filter_cdrh3_design("WGGDGFYAMDY", "")
        assert accepted


class TestCalibratedThresholds:
    """Thresholds must not flag the majority of real antibodies as abnormal."""

    def test_approved_cdrh3_lengths_are_within_the_allowed_range(self):
        from biochat.tool.antibody_design.generation_filter import ALLOWED_MAX_LEN, ALLOWED_MIN_LEN

        # Nivolumab (4aa) and secukinumab (18aa) bracket the approved cohort.
        assert ALLOWED_MIN_LEN <= 4
        assert ALLOWED_MAX_LEN >= 18

    def test_gates_share_one_length_definition(self):
        from biochat.tool.antibody_design import generation_filter, sequence_qc

        assert sequence_qc.ALLOWED_MIN_LEN == generation_filter.ALLOWED_MIN_LEN
        assert sequence_qc.ALLOWED_MAX_LEN == generation_filter.ALLOWED_MAX_LEN

    def test_short_loop_escapes_the_single_aa_fraction_rule(self):
        from biochat.tool.antibody_design.sequence_qc import run_full_qc

        # `NDDY` is nivolumab's CDR-H3: D is 50% of a 4-residue loop, which a
        # bare fraction rule reads as a hard failure.
        flags = run_full_qc("NDDY")["sequence_qc"]["flags"]
        assert not any(f.startswith("excessive_single_aa") for f in flags)

    def test_genuine_single_aa_excess_still_fails(self):
        from biochat.tool.antibody_design.sequence_qc import run_full_qc

        flags = run_full_qc("DDDDDDGYAMDY")["sequence_qc"]["flags"]
        assert any(f.startswith("excessive_single_aa") for f in flags)

    def test_aromatic_threshold_is_deterministic(self):
        from biochat.tool.antibody_design.generation_filter import filter_cdrh3_design

        # AROMATIC is a set; without sorting, which single-residue flag fires
        # would depend on iteration order.
        first = filter_cdrh3_design("YYYYYWWWFFF", "")[1]
        for _ in range(5):
            assert filter_cdrh3_design("YYYYYWWWFFF", "")[1] == first


class TestBenchmarkStatistics:
    def test_mann_whitney_auc_bounds(self):
        from biochat.eval.antibody_benchmark import mann_whitney_u

        assert mann_whitney_u([3, 4, 5], [0, 1, 2])[1] == 1.0
        assert mann_whitney_u([0, 1, 2], [3, 4, 5])[1] == 0.0
        assert mann_whitney_u([1, 1], [1, 1])[1] == 0.5

    def test_shuffled_decoys_preserve_composition(self):
        from biochat.eval.antibody_benchmark import shuffled_decoys

        originals = ["WGGDGFYAMDY", "YPHYYGSSHWYFDV"]
        for original, decoy in zip(originals, shuffled_decoys(originals, seed=7), strict=True):
            assert sorted(decoy) == sorted(original)

    def test_random_decoys_match_requested_lengths(self):
        from biochat.eval.antibody_benchmark import VALID_AAS, random_decoys

        decoys = random_decoys([5, 11, 20], seed=7)
        assert [len(d) for d in decoys] == [5, 11, 20]
        assert all(c in VALID_AAS for d in decoys for c in d)

    def test_percentiles_are_ordered(self):
        from biochat.eval.antibody_benchmark import describe

        stats = describe([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        assert stats["p5"] <= stats["p25"] <= stats["p50"] <= stats["p75"] <= stats["p95"]


class TestBenchmarkScript:
    def test_runner_reproduces_the_committed_dataset(self):
        result = subprocess.run(
            [sys.executable, "scripts/run_antibody_benchmark.py", "--tag", "pytest"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert result.returncode == 0, result.stderr[-800:]
        assert "已获批药物通过率" in result.stdout
        (ROOT / "reports" / "antibody_benchmark_results_pytest.csv").unlink(missing_ok=True)
        (ROOT / "reports" / "antibody_benchmark_summary_pytest.json").unlink(missing_ok=True)
        (ROOT / "reports" / "antibody_benchmark_report_pytest.md").unlink(missing_ok=True)


class TestCDRH3BigramModel:
    """The adjacency model must be composition-controlled by construction."""

    CORPUS = [
        "ARDYGSSYFDY", "AKDRGYSSGWFDV", "ARGGYSSSWYFDY", "ASDYYGSGSYFDY",
        "AKDGYSSGWFDY", "ARSSGWYFDV", "ATDYGDYGMDV", "ARDLGYYFDY",
        "AKGYSSGWYFDV", "ARDYYGSGSAMDY", "ARGDYGMDV", "AKDSSGWFDY",
    ]

    def _model(self):
        from biochat.eval.cdrh3_lm import CDRH3BigramModel

        return CDRH3BigramModel.fit(self.CORPUS)

    def test_real_corpus_outscores_its_own_shuffles(self):
        from biochat.eval.antibody_benchmark import mann_whitney_u, shuffled_decoys

        model = self._model()
        real = model.score_many(self.CORPUS)
        shuffled = model.score_many(shuffled_decoys(self.CORPUS, seed=3))
        assert mann_whitney_u(real, shuffled)[1] > 0.5

    def test_short_and_empty_sequences_score_zero(self):
        model = self._model()
        assert model.score("") == 0.0
        assert model.score("A") == 0.0

    def test_noncanonical_residues_are_skipped_not_fatal(self):
        model = self._model()
        assert isinstance(model.score("ARDXYGMDY"), float)

    def test_round_trips_through_json(self, tmp_path):
        from biochat.eval.cdrh3_lm import CDRH3BigramModel

        model = self._model()
        path = model.save(tmp_path / "m.json")
        reloaded = CDRH3BigramModel.load(path)
        assert reloaded.score("ARDYGSSYFDY") == model.score("ARDYGSSYFDY")
        assert reloaded.n_train == model.n_train

    def test_load_rejects_a_foreign_file(self, tmp_path):
        import json

        import pytest

        from biochat.eval.cdrh3_lm import CDRH3BigramModel

        path = tmp_path / "other.json"
        path.write_text(json.dumps({"model": "something_else"}))
        with pytest.raises(ValueError):
            CDRH3BigramModel.load(path)

    def test_top_motifs_require_support(self):
        from biochat.eval.cdrh3_lm import top_motifs

        model = self._model()
        # Without a support floor, add-alpha smoothing lets pairs seen once or
        # twice outrank pairs seen hundreds of times.
        assert top_motifs(model, n=5, min_count=1000) == []
        for _pair, _pmi, count in top_motifs(model, n=5, min_count=3):
            assert count >= 3

    def test_cross_validation_returns_one_score_per_fold(self):
        from biochat.eval.cdrh3_lm import cross_validate

        folds = cross_validate(self.CORPUS, folds=4)
        assert len(folds) == 4
        assert all(isinstance(f, float) for f in folds)


class TestAntibodyLikenessSideChannel:
    """The likeness signal is reported but must never influence ranking."""

    SEQUENCES = [
        "WGGDGFYAMDY", "YPHYYGSSHWYFDV", "NDDY",
        "CLFRNERYSYA", "STYYGGDWYFNV", "DYYDILTDYYIHYWYFDL",
    ]
    EPITOPE = "LHCPALVTYNTDTFESM"

    def _rank(self):
        from biochat.tool.antibody_design.api import score_and_rank_candidates

        result = score_and_rank_candidates(self.SEQUENCES, self.EPITOPE)
        return [
            (c["cdrh3_sequence"], c["rank"], c["aggregate_score"], c["accepted"])
            for c in result["candidates"]
        ], result

    def test_ranking_is_identical_with_and_without_the_model(self, monkeypatch):
        from biochat.tool.antibody_design import antibody_likeness

        antibody_likeness.reset_cache()
        with_model, result = self._rank()
        assert any("antibody_likeness" in c["scores"] for c in result["candidates"])

        # Point the loader at a path that does not exist: the signal disappears,
        # everything the pipeline actually decides on must stay byte-identical.
        monkeypatch.setenv("BIOCHAT_CDRH3_LM_PATH", "/nonexistent/cdrh3_model.json")
        antibody_likeness.reset_cache()
        without_model, bare = self._rank()

        assert not any("antibody_likeness" in c["scores"] for c in bare["candidates"])
        assert with_model == without_model

        antibody_likeness.reset_cache()

    def test_missing_artifact_degrades_silently(self, monkeypatch):
        from biochat.tool.antibody_design import antibody_likeness

        monkeypatch.setenv("BIOCHAT_CDRH3_LM_PATH", "/nonexistent/cdrh3_model.json")
        antibody_likeness.reset_cache()
        assert antibody_likeness.score_antibody_likeness("WGGDGFYAMDY") is None
        antibody_likeness.reset_cache()

    def test_corrupt_artifact_degrades_silently(self, monkeypatch, tmp_path):
        from biochat.tool.antibody_design import antibody_likeness

        broken = tmp_path / "broken.json"
        broken.write_text("{not valid json")
        monkeypatch.setenv("BIOCHAT_CDRH3_LM_PATH", str(broken))
        antibody_likeness.reset_cache()
        assert antibody_likeness.score_antibody_likeness("WGGDGFYAMDY") is None
        antibody_likeness.reset_cache()

    def test_record_is_labelled_as_non_ranking_and_non_affinity(self):
        from biochat.tool.antibody_design import antibody_likeness

        antibody_likeness.reset_cache()
        record = antibody_likeness.score_antibody_likeness("WGGDGFYAMDY")
        if record is None:  # no trained artifact in this checkout
            return
        assert record["ranking_input"] is False
        assert record["provenance"] == "model_inferred"
        assert record["calibration"] == "uncalibrated"
        # The pipeline forbids presenting computed scores as experimental ones.
        for forbidden in ("affinity", "ΔG", "Kd"):
            assert forbidden in record["interpretation"] or forbidden.lower() in record["interpretation"].lower()

    def test_sequence_too_short_for_a_pair_yields_no_signal(self):
        from biochat.tool.antibody_design import antibody_likeness

        antibody_likeness.reset_cache()
        assert antibody_likeness.score_antibody_likeness("A") is None
        assert antibody_likeness.score_antibody_likeness("") is None
