"""Tests for etip_core.schemas — DTO validation."""

import pytest
from pydantic import ValidationError

import etip_core.schemas as core_schemas
from etip_core.schemas import EmployeeDTO, ProjectDTO, SkillDTO, SyncResultDTO


class TestEmployeeDTO:
    def test_valid_minimal(self):
        dto = EmployeeDTO(
            external_id="abc123",
            email="user@example.com",
            full_name="Jane Doe",
            source="okta",
        )
        assert dto.email == "user@example.com"
        assert dto.raw == {}

    def test_valid_full(self):
        dto = EmployeeDTO(
            external_id="abc123",
            email="user@example.com",
            full_name="Jane Doe",
            title="Senior Engineer",
            department="Engineering",
            manager_email="boss@example.com",
            source="hris",
            raw={"id": "abc123"},
        )
        assert dto.title == "Senior Engineer"
        assert dto.raw == {"id": "abc123"}

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError):
            EmployeeDTO(
                external_id="x",
                email="not-an-email",
                full_name="Jane",
                source="okta",
            )

    def test_optional_fields_default_none(self):
        dto = EmployeeDTO(external_id="x", email="a@b.com", full_name="X", source="test")
        assert dto.title is None
        assert dto.department is None
        assert dto.manager_email is None


class TestSkillDTO:
    def test_valid_minimal(self):
        dto = SkillDTO(raw_label="python3", source="github")
        assert dto.raw_label == "python3"
        assert dto.confidence_score == 0.5
        assert dto.evidence == {}

    def test_confidence_score_clamped(self):
        with pytest.raises(ValidationError):
            SkillDTO(raw_label="x", source="github", confidence_score=1.5)

        with pytest.raises(ValidationError):
            SkillDTO(raw_label="x", source="github", confidence_score=-0.1)

    def test_nivel_optional(self):
        dto = SkillDTO(raw_label="go", source="github")
        assert dto.nivel is None

    def test_with_esco_uri(self):
        dto = SkillDTO(
            raw_label="python3",
            esco_uri="http://data.europa.eu/esco/skill/123",
            esco_label="Python (programming language)",
            source="github",
            confidence_score=0.9,
        )
        assert dto.esco_label == "Python (programming language)"


class TestProjectDTO:
    def test_valid(self):
        dto = ProjectDTO(external_id="PROJ-1", name="My Project", source="jira")
        assert dto.description is None
        assert dto.raw == {}

    def test_with_description(self):
        dto = ProjectDTO(
            external_id="PROJ-1",
            name="My Project",
            description="Does things",
            source="jira",
        )
        assert dto.description == "Does things"


class TestSyncResultDTO:
    def test_valid(self):
        from datetime import datetime, UTC

        result = SyncResultDTO(
            connector="github",
            tenant_id="tenant-1",
            employees_synced=10,
            skills_synced=50,
            errors=[],
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
        )
        assert result.projects_synced == 0
        assert result.errors == []

    def test_with_errors(self):
        from datetime import datetime, UTC

        result = SyncResultDTO(
            connector="jira",
            tenant_id="t",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            errors=["timeout on page 2"],
        )
        assert len(result.errors) == 1


class TestCoreSchemasBoundary:
    """etip_core.schemas must only expose connector DTOs, not API response shapes."""

    def test_recommendation_out_not_in_core(self):
        assert not hasattr(core_schemas, "RecommendationOut")

    def test_employee_out_not_in_core(self):
        assert not hasattr(core_schemas, "EmployeeOut")

    def test_skill_out_not_in_core(self):
        assert not hasattr(core_schemas, "SkillOut")

    def test_connector_dtos_still_present(self):
        assert hasattr(core_schemas, "EmployeeDTO")
        assert hasattr(core_schemas, "SkillDTO")
        assert hasattr(core_schemas, "ProjectDTO")
        assert hasattr(core_schemas, "SyncResultDTO")

    def test_recommendation_out_importable_from_api_schemas(self):
        from etip_api.schemas.recommendations import RecommendationOut, SkillMatch
        assert RecommendationOut.model_fields
        assert SkillMatch.model_fields
