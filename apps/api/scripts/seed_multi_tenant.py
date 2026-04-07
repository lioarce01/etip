"""
Seed the platform with a platform admin, multiple tenants, and test data.

Usage (from repo root):
    uv run python apps/api/scripts/seed_multi_tenant.py

The script is idempotent — running it twice is safe.
This creates:
  - 1 platform admin user (can see all tenants)
  - 3 test tenants (acme, startech, innovate)
  - Each tenant has:
    - 1 admin user
    - 2-3 regular users (tm, dev roles)
    - 2 projects
    - 8 employees with skills
"""

import asyncio
import sys
import uuid
from datetime import date

sys.path.insert(0, "apps/api/src")
sys.path.insert(0, "apps/api/core/src")

from sqlalchemy import select
from etip_api.database import AsyncSessionLocal
from etip_api.models.tenant import Tenant
from etip_api.models.user import User
from etip_api.models.employee import Employee
from etip_api.models.skill import Skill, EmployeeSkill
from etip_api.models.project import Project
from etip_api.auth.password import hash_password


# ── Platform Admin ────────────────────────────────────────────────────────────

PLATFORM_ADMIN = {
    "email": "admin@platform.local",
    "password": "PlatformAdmin123",
}

# ── Tenants Configuration ─────────────────────────────────────────────────────

TENANTS_CONFIG = [
    {
        "slug": "acme",
        "name": "ACME Corporation",
        "admin_email": "admin@acme.local",
        "admin_password": "AcmeAdmin123",
        "users": [
            {"email": "alice@acme.local", "password": "Password123", "role": "tm"},
            {"email": "bob@acme.local", "password": "Password123", "role": "dev"},
            {"email": "carol@acme.local", "password": "Password123", "role": "dev"},
        ],
        "projects": [
            {
                "name": "Mobile App Redesign",
                "description": "Complete redesign of our mobile app for iOS and Android",
                "status": "active",
                "start_date": date(2026, 2, 1),
                "end_date": date(2026, 8, 31),
                "required_skills": [
                    {"skill_label": "React", "level": "senior", "weight": 1.0},
                    {"skill_label": "TypeScript", "level": "senior", "weight": 0.9},
                    {"skill_label": "AWS", "level": "mid", "weight": 0.6},
                ],
            },
            {
                "name": "API Performance Optimization",
                "description": "Optimize existing APIs for 10x performance improvement",
                "status": "planning",
                "start_date": date(2026, 3, 15),
                "end_date": date(2026, 6, 30),
                "required_skills": [
                    {"skill_label": "Python", "level": "senior", "weight": 1.0},
                    {"skill_label": "PostgreSQL", "level": "senior", "weight": 0.9},
                    {"skill_label": "Docker", "level": "mid", "weight": 0.7},
                ],
            },
        ],
    },
    {
        "slug": "startech",
        "name": "StarTech Industries",
        "admin_email": "admin@startech.local",
        "admin_password": "StarTechAdmin123",
        "users": [
            {"email": "dev@startech.local", "password": "Password123", "role": "tm"},
            {"email": "engineer@startech.local", "password": "Password123", "role": "dev"},
        ],
        "projects": [
            {
                "name": "Cloud Migration",
                "description": "Migrate on-premise infrastructure to AWS cloud",
                "status": "active",
                "start_date": date(2026, 1, 15),
                "end_date": date(2026, 7, 31),
                "required_skills": [
                    {"skill_label": "AWS", "level": "senior", "weight": 1.0},
                    {"skill_label": "Kubernetes", "level": "senior", "weight": 0.9},
                    {"skill_label": "Terraform", "level": "mid", "weight": 0.8},
                ],
            },
        ],
    },
    {
        "slug": "innovate",
        "name": "InnovateLabs",
        "admin_email": "admin@innovate.local",
        "admin_password": "InnovateAdmin123",
        "users": [
            {"email": "researcher@innovate.local", "password": "Password123", "role": "tm"},
            {"email": "scientist@innovate.local", "password": "Password123", "role": "dev"},
            {"email": "analyst@innovate.local", "password": "Password123", "role": "dev"},
        ],
        "projects": [
            {
                "name": "ML Pipeline Development",
                "description": "Build and deploy machine learning pipeline for predictions",
                "status": "active",
                "start_date": date(2026, 2, 1),
                "end_date": date(2026, 9, 30),
                "required_skills": [
                    {"skill_label": "Machine Learning", "level": "senior", "weight": 1.0},
                    {"skill_label": "Python", "level": "senior", "weight": 0.95},
                    {"skill_label": "Data Analysis", "level": "senior", "weight": 0.9},
                ],
            },
            {
                "name": "Data Warehouse Setup",
                "description": "Build scalable data warehouse for analytics",
                "status": "planning",
                "start_date": date(2026, 4, 1),
                "end_date": date(2026, 12, 31),
                "required_skills": [
                    {"skill_label": "PostgreSQL", "level": "senior", "weight": 1.0},
                    {"skill_label": "AWS", "level": "mid", "weight": 0.8},
                    {"skill_label": "Python", "level": "mid", "weight": 0.7},
                ],
            },
        ],
    },
]

# ── Shared Employee & Skill Data ──────────────────────────────────────────────

SKILLS_DATA = [
    "Python", "TypeScript", "React", "FastAPI", "PostgreSQL",
    "Docker", "Kubernetes", "AWS", "Machine Learning", "Data Analysis",
    "Go", "Rust", "GraphQL", "Redis", "Terraform",
]

EMPLOYEES_DATA = [
    {
        "full_name": "Alice Martin",
        "title": "Senior Backend Engineer",
        "department": "Engineering",
        "skills": [("Python", "senior"), ("FastAPI", "senior"), ("PostgreSQL", "mid")],
    },
    {
        "full_name": "Bob Chen",
        "title": "Full-Stack Engineer",
        "department": "Engineering",
        "skills": [("TypeScript", "senior"), ("React", "senior"), ("Python", "mid")],
    },
    {
        "full_name": "Carol Singh",
        "title": "ML Engineer",
        "department": "Data",
        "skills": [("Python", "senior"), ("Machine Learning", "senior"), ("Data Analysis", "senior")],
    },
    {
        "full_name": "David Lee",
        "title": "DevOps Engineer",
        "department": "Infrastructure",
        "skills": [("Docker", "senior"), ("Kubernetes", "senior"), ("Terraform", "senior")],
    },
    {
        "full_name": "Eva Rossi",
        "title": "Frontend Engineer",
        "department": "Engineering",
        "skills": [("React", "senior"), ("TypeScript", "senior"), ("GraphQL", "mid")],
    },
    {
        "full_name": "Frank Müller",
        "title": "Backend Engineer",
        "department": "Engineering",
        "skills": [("Go", "senior"), ("PostgreSQL", "senior"), ("Redis", "mid")],
    },
    {
        "full_name": "Grace Tanaka",
        "title": "Data Analyst",
        "department": "Data",
        "skills": [("Python", "mid"), ("Data Analysis", "senior"), ("PostgreSQL", "mid")],
    },
    {
        "full_name": "Henry Park",
        "title": "Platform Engineer",
        "department": "Infrastructure",
        "skills": [("Kubernetes", "mid"), ("Rust", "mid"), ("Go", "mid")],
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
        # ── Create or get platform admin ──────────────────────────────────────

        platform_admin = await db.scalar(
            select(User).where(User.email == PLATFORM_ADMIN["email"])
        )
        if not platform_admin:
            print("[seed] Creating platform admin user...")
            # Platform admin needs a tenant, use the first one (will be created below)
            # For now, just create a placeholder tenant
            temp_tenant = Tenant(name="Platform", slug="platform-internal")
            db.add(temp_tenant)
            await db.flush()

            platform_admin = User(
                id=uuid.uuid4(),
                tenant_id=temp_tenant.id,
                email=PLATFORM_ADMIN["email"],
                hashed_password=hash_password(PLATFORM_ADMIN["password"]),
                role="admin",
                is_platform_admin=True,
            )
            db.add(platform_admin)
            await db.flush()
            print(f"[seed] + Platform admin: {PLATFORM_ADMIN['email']} / {PLATFORM_ADMIN['password']}")

        # ── Build skill map (global) ──────────────────────────────────────────

        skill_map = {}
        for label in SKILLS_DATA:
            skill_map[label] = await get_or_create_skill(db, label)
        await db.flush()

        # ── Seed each tenant ──────────────────────────────────────────────────

        for tenant_cfg in TENANTS_CONFIG:
            tenant = await db.scalar(select(Tenant).where(Tenant.slug == tenant_cfg["slug"]))
            if not tenant:
                print(f"\n[seed] Creating tenant '{tenant_cfg['slug']}'...")
                tenant = Tenant(name=tenant_cfg["name"], slug=tenant_cfg["slug"])
                db.add(tenant)
                await db.flush()

                # Create admin user for this tenant
                admin = User(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    email=tenant_cfg["admin_email"],
                    hashed_password=hash_password(tenant_cfg["admin_password"]),
                    role="admin",
                    is_platform_admin=False,
                )
                db.add(admin)
                print(f"  + Admin: {tenant_cfg['admin_email']} / {tenant_cfg['admin_password']}")

                # Create regular users
                for user_data in tenant_cfg["users"]:
                    user = User(
                        id=uuid.uuid4(),
                        tenant_id=tenant.id,
                        email=user_data["email"],
                        hashed_password=hash_password(user_data["password"]),
                        role=user_data["role"],
                    )
                    db.add(user)
                    print(f"  + User ({user_data['role']}): {user_data['email']}")

                await db.flush()

                # Create employees
                for emp_data in EMPLOYEES_DATA:
                    emp = Employee(
                        id=uuid.uuid4(),
                        tenant_id=tenant.id,
                        email=f"{emp_data['full_name'].lower().replace(' ', '.')}@{tenant_cfg['slug']}.local",
                        full_name=emp_data["full_name"],
                        title=emp_data["title"],
                        department=emp_data["department"],
                    )
                    db.add(emp)
                    await db.flush()

                    # Add skills
                    for skill_label, nivel in emp_data["skills"]:
                        skill = skill_map[skill_label]
                        db.add(
                            EmployeeSkill(
                                id=uuid.uuid4(),
                                tenant_id=tenant.id,
                                employee_id=emp.id,
                                skill_id=skill.id,
                                nivel=nivel,
                                confidence_score=0.9,
                                source="manual",
                            )
                        )
                    print(f"  + Employee: {emp_data['full_name']}")

                await db.flush()

                # Create projects
                for proj_data in tenant_cfg["projects"]:
                    db.add(
                        Project(
                            id=uuid.uuid4(),
                            tenant_id=tenant.id,
                            name=proj_data["name"],
                            description=proj_data["description"],
                            status=proj_data["status"],
                            start_date=proj_data["start_date"],
                            end_date=proj_data.get("end_date"),
                            required_skills=proj_data["required_skills"],
                        )
                    )
                    print(f"  + Project: {proj_data['name']}")

        await db.commit()
        print("\n[seed] SUCCESS! Seeding complete!")
        print("\n" + "=" * 70)
        print("TEST CREDENTIALS")
        print("=" * 70)
        print(f"\nPlatform Admin (access to all tenants):")
        print(f"  Email:    {PLATFORM_ADMIN['email']}")
        print(f"  Password: {PLATFORM_ADMIN['password']}")
        print(f"\nTenant Admins:")
        for cfg in TENANTS_CONFIG:
            print(f"  {cfg['name']} ({cfg['slug']}):")
            print(f"    Email:    {cfg['admin_email']}")
            print(f"    Password: {cfg['admin_password']}")
        print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(seed())
