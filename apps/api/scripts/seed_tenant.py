"""
Seed a tenant with users, employees, skills, and projects.

Usage (from repo root):
    uv run python apps/api/scripts/seed_tenant.py

The script is idempotent — running it twice is safe.
Edit the TENANT_SLUG at the top to target a different workspace.
"""

import asyncio
import sys
import uuid
from datetime import date

TENANT_SLUG = "test1"

sys.path.insert(0, "apps/api/src")
sys.path.insert(0, "apps/api/core/src")

from sqlalchemy import select, text
from etip_api.database import AsyncSessionLocal
from etip_api.models.tenant import Tenant
from etip_api.models.user import User
from etip_api.models.employee import Employee
from etip_api.models.skill import Skill, EmployeeSkill
from etip_api.models.project import Project
from etip_api.auth.password import hash_password


# ── Seed data ─────────────────────────────────────────────────────────────────

EXTRA_USERS = [
    {"email": "alice@test1.com",   "password": "Password123", "role": "tm"},
    {"email": "bob@test1.com",     "password": "Password123", "role": "dev"},
    {"email": "carol@test1.com",   "password": "Password123", "role": "dev"},
]

SKILLS_DATA = [
    "Python", "TypeScript", "React", "FastAPI", "PostgreSQL",
    "Docker", "Kubernetes", "AWS", "Machine Learning", "Data Analysis",
    "Go", "Rust", "GraphQL", "Redis", "Terraform",
]

EMPLOYEES_DATA = [
    {
        "full_name": "Alice Martin",
        "email": "alice.martin@test1.com",
        "title": "Senior Backend Engineer",
        "department": "Engineering",
        "skills": [("Python", "senior"), ("FastAPI", "senior"), ("PostgreSQL", "mid"), ("Docker", "mid")],
    },
    {
        "full_name": "Bob Chen",
        "email": "bob.chen@test1.com",
        "title": "Full-Stack Engineer",
        "department": "Engineering",
        "skills": [("TypeScript", "senior"), ("React", "senior"), ("Python", "mid"), ("PostgreSQL", "junior")],
    },
    {
        "full_name": "Carol Singh",
        "email": "carol.singh@test1.com",
        "title": "ML Engineer",
        "department": "Data",
        "skills": [("Python", "senior"), ("Machine Learning", "senior"), ("Data Analysis", "senior"), ("AWS", "mid")],
    },
    {
        "full_name": "David Lee",
        "email": "david.lee@test1.com",
        "title": "DevOps Engineer",
        "department": "Infrastructure",
        "skills": [("Docker", "senior"), ("Kubernetes", "senior"), ("Terraform", "senior"), ("AWS", "senior")],
    },
    {
        "full_name": "Eva Rossi",
        "email": "eva.rossi@test1.com",
        "title": "Frontend Engineer",
        "department": "Engineering",
        "skills": [("React", "senior"), ("TypeScript", "senior"), ("GraphQL", "mid")],
    },
    {
        "full_name": "Frank Müller",
        "email": "frank.muller@test1.com",
        "title": "Backend Engineer",
        "department": "Engineering",
        "skills": [("Go", "senior"), ("PostgreSQL", "senior"), ("Redis", "mid"), ("Docker", "mid")],
    },
    {
        "full_name": "Grace Tanaka",
        "email": "grace.tanaka@test1.com",
        "title": "Data Analyst",
        "department": "Data",
        "skills": [("Python", "mid"), ("Data Analysis", "senior"), ("PostgreSQL", "mid")],
    },
    {
        "full_name": "Henry Park",
        "email": "henry.park@test1.com",
        "title": "Platform Engineer",
        "department": "Infrastructure",
        "skills": [("Kubernetes", "mid"), ("Rust", "mid"), ("Go", "mid"), ("Terraform", "mid")],
    },
]

PROJECTS_DATA = [
    {
        "name": "Platform Modernisation",
        "description": "Migrate monolith services to containerised microservices on Kubernetes.",
        "status": "active",
        "start_date": date(2026, 1, 15),
        "end_date": date(2026, 9, 30),
        "required_skills": [
            {"skill_label": "Kubernetes", "level": "senior", "weight": 1.0},
            {"skill_label": "Docker",     "level": "mid",    "weight": 0.8},
            {"skill_label": "Terraform",  "level": "mid",    "weight": 0.7},
            {"skill_label": "Go",         "level": "mid",    "weight": 0.6},
        ],
    },
    {
        "name": "ML Recommendation Engine",
        "description": "Build a real-time recommendation service using embeddings and vector search.",
        "status": "planning",
        "start_date": date(2026, 4, 1),
        "end_date": date(2026, 12, 31),
        "required_skills": [
            {"skill_label": "Machine Learning", "level": "senior", "weight": 1.0},
            {"skill_label": "Python",           "level": "senior", "weight": 0.9},
            {"skill_label": "AWS",              "level": "mid",    "weight": 0.6},
        ],
    },
    {
        "name": "Customer Portal Redesign",
        "description": "Rebuild the customer-facing portal with a modern React + GraphQL stack.",
        "status": "active",
        "start_date": date(2026, 2, 1),
        "end_date": date(2026, 7, 31),
        "required_skills": [
            {"skill_label": "React",      "level": "senior", "weight": 1.0},
            {"skill_label": "TypeScript", "level": "senior", "weight": 0.9},
            {"skill_label": "GraphQL",    "level": "mid",    "weight": 0.7},
        ],
    },
    {
        "name": "Data Warehouse Migration",
        "description": "Move analytics pipeline from legacy warehouse to cloud-native solution.",
        "status": "on_hold",
        "start_date": date(2026, 6, 1),
        "end_date": None,
        "required_skills": [
            {"skill_label": "Data Analysis", "level": "senior", "weight": 1.0},
            {"skill_label": "Python",        "level": "mid",    "weight": 0.8},
            {"skill_label": "PostgreSQL",    "level": "senior", "weight": 0.8},
            {"skill_label": "AWS",           "level": "mid",    "weight": 0.6},
        ],
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def get_or_create_skill(db, label: str) -> Skill:
    skill = await db.scalar(select(Skill).where(Skill.preferred_label == label))
    if not skill:
        skill = Skill(id=uuid.uuid4(), preferred_label=label)
        db.add(skill)
        await db.flush()
    return skill


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        # ── Resolve or create tenant ──────────────────────────────────────────
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == TENANT_SLUG))
        if not tenant:
            print(f"[seed] tenant '{TENANT_SLUG}' not found. Creating...")
            tenant = Tenant(name="Test Company", slug=TENANT_SLUG)
            db.add(tenant)
            await db.flush()
            # Create admin user
            admin = User(
                tenant_id=tenant.id,
                email=f"admin@{TENANT_SLUG}.com",
                hashed_password=hash_password("Password123"),
                role="admin",
            )
            db.add(admin)
            await db.flush()
            print(f"[seed] created tenant '{tenant.slug}' (id={tenant.id})")
            print(f"[seed] created admin user: admin@{TENANT_SLUG}.com / Password123")

        print(f"[seed] seeding tenant '{tenant.slug}' (id={tenant.id})")
        await db.execute(text("SET LOCAL rls.tenant_id = :tid").bindparams(tid=str(tenant.id)))

        # ── Extra users ───────────────────────────────────────────────────────
        for u in EXTRA_USERS:
            exists = await db.scalar(
                select(User).where(User.tenant_id == tenant.id, User.email == u["email"])
            )
            if not exists:
                db.add(User(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    email=u["email"],
                    hashed_password=hash_password(u["password"]),
                    role=u["role"],
                ))
                print(f"  + user {u['email']} ({u['role']})")

        await db.flush()

        # ── Skills (global) ───────────────────────────────────────────────────
        skill_map: dict[str, Skill] = {}
        for label in SKILLS_DATA:
            skill_map[label] = await get_or_create_skill(db, label)

        await db.flush()

        # ── Employees ─────────────────────────────────────────────────────────
        for emp_data in EMPLOYEES_DATA:
            exists = await db.scalar(
                select(Employee).where(
                    Employee.tenant_id == tenant.id,
                    Employee.email == emp_data["email"],
                )
            )
            if exists:
                continue

            emp = Employee(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                email=emp_data["email"],
                full_name=emp_data["full_name"],
                title=emp_data["title"],
                department=emp_data["department"],
            )
            db.add(emp)
            await db.flush()

            for skill_label, nivel in emp_data["skills"]:
                skill = skill_map[skill_label]
                db.add(EmployeeSkill(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    employee_id=emp.id,
                    skill_id=skill.id,
                    nivel=nivel,
                    confidence_score=0.9,
                    source="manual",
                ))

            print(f"  + employee {emp_data['full_name']}")

        await db.flush()

        # ── Projects ──────────────────────────────────────────────────────────
        for proj_data in PROJECTS_DATA:
            exists = await db.scalar(
                select(Project).where(
                    Project.tenant_id == tenant.id,
                    Project.name == proj_data["name"],
                )
            )
            if exists:
                continue

            db.add(Project(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                name=proj_data["name"],
                description=proj_data["description"],
                status=proj_data["status"],
                start_date=proj_data["start_date"],
                end_date=proj_data["end_date"],
                required_skills=proj_data["required_skills"],
            ))
            print(f"  + project '{proj_data['name']}'")

        await db.commit()
        print("[seed] done.")


if __name__ == "__main__":
    asyncio.run(seed())
