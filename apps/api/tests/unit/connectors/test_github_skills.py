"""Tests for etip_connector_github.skills — skill inference from repo data."""

import pytest

from etip_connector_github.skills import infer_skills_from_repos, _infer_nivel


class TestInferNivel:
    def test_high_pct_returns_senior(self):
        assert _infer_nivel(0.45) == "senior"
        assert _infer_nivel(1.0) == "senior"

    def test_mid_range_returns_mid(self):
        assert _infer_nivel(0.15) == "mid"
        assert _infer_nivel(0.39) == "mid"

    def test_low_pct_returns_junior(self):
        assert _infer_nivel(0.0) == "junior"
        assert _infer_nivel(0.14) == "junior"


class TestInferSkillsFromRepos:
    def _make_repo(self, name: str, topics: list[str] | None = None) -> dict:
        return {"full_name": name, "topics": topics or []}

    def test_language_bytes_converted_to_skills(self):
        repos = [self._make_repo("acme/api")]
        langs = {"acme/api": {"Python": 80000, "SQL": 20000}}

        skills = infer_skills_from_repos(repos, langs)
        labels = [s["raw_label"] for s in skills]

        assert "Python" in labels
        assert "SQL" in labels

    def test_python_dominant_gets_senior_nivel(self):
        repos = [self._make_repo("acme/api")]
        langs = {"acme/api": {"Python": 90000, "HTML": 10000}}

        skills = infer_skills_from_repos(repos, langs)
        python_skill = next(s for s in skills if s["raw_label"] == "Python")

        assert python_skill["nivel"] == "senior"

    def test_minor_language_gets_junior_nivel(self):
        repos = [self._make_repo("acme/api")]
        langs = {"acme/api": {"Python": 90000, "Dockerfile": 5000}}

        skills = infer_skills_from_repos(repos, langs)
        docker_skill = next((s for s in skills if s["raw_label"] == "Dockerfile"), None)

        assert docker_skill is not None
        assert docker_skill["nivel"] == "junior"

    def test_topic_based_skills_added(self):
        repos = [self._make_repo("acme/infra", topics=["terraform", "kubernetes"])]
        langs = {"acme/infra": {"HCL": 50000}}

        skills = infer_skills_from_repos(repos, langs)
        raw_labels = [s["raw_label"] for s in skills]

        assert "terraform" in raw_labels
        assert "kubernetes" in raw_labels

    def test_topic_skills_have_fixed_confidence(self):
        repos = [self._make_repo("acme/infra", topics=["docker"])]
        skills = infer_skills_from_repos(repos, {})
        docker_skill = next(s for s in skills if s["raw_label"] == "docker")
        assert docker_skill["confidence_score"] == 0.6

    def test_language_confidence_scales_with_volume(self):
        repos = [self._make_repo("acme/api")]
        langs = {
            "acme/api": {"Python": 95000, "Shell": 5000},
        }
        skills = infer_skills_from_repos(repos, langs)

        python_skill = next(s for s in skills if s["raw_label"] == "Python")
        shell_skill = next(s for s in skills if s["raw_label"] == "Shell")

        assert python_skill["confidence_score"] > shell_skill["confidence_score"]

    def test_evidence_contains_bytes_and_pct(self):
        repos = [self._make_repo("acme/api")]
        langs = {"acme/api": {"Go": 100000}}

        skills = infer_skills_from_repos(repos, langs)
        go_skill = next(s for s in skills if s["raw_label"] == "Go")

        assert "bytes" in go_skill["evidence"]
        assert "pct_of_total" in go_skill["evidence"]

    def test_all_skills_have_github_source(self):
        repos = [self._make_repo("acme/api", topics=["docker"])]
        langs = {"acme/api": {"Python": 1000}}

        skills = infer_skills_from_repos(repos, langs)
        assert all(s["source"] == "github" for s in skills)

    def test_unknown_language_uses_raw_label(self):
        repos = [self._make_repo("acme/app")]
        langs = {"acme/app": {"CoolLang": 50000}}

        skills = infer_skills_from_repos(repos, langs)
        skill = next(s for s in skills if s["raw_label"] == "CoolLang")
        assert skill is not None

    def test_empty_repos_returns_empty(self):
        skills = infer_skills_from_repos([], {})
        assert skills == []

    def test_multiple_repos_aggregate_language_bytes(self):
        repos = [self._make_repo("acme/api"), self._make_repo("acme/worker")]
        langs = {
            "acme/api": {"Python": 50000},
            "acme/worker": {"Python": 50000},
        }
        skills = infer_skills_from_repos(repos, langs)
        python_skill = next(s for s in skills if s["raw_label"] == "Python")
        assert python_skill["evidence"]["bytes"] == 100000
