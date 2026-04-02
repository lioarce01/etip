"""
Skill inference from GitHub data.

Strategy:
  1. Language bytes → language skill with confidence based on % of total code
  2. Repo topics → additional skill signals
  3. Framework detection via common repo name patterns and topics
"""

# Mapping of GitHub language names → normalized skill labels
LANGUAGE_SKILL_MAP: dict[str, str] = {
    "Python": "Python",
    "TypeScript": "TypeScript",
    "JavaScript": "JavaScript",
    "Go": "Go (programming language)",
    "Rust": "Rust (programming language)",
    "Java": "Java",
    "Kotlin": "Kotlin",
    "Swift": "Swift",
    "C#": "C#",
    "C++": "C++",
    "Ruby": "Ruby",
    "PHP": "PHP",
    "Scala": "Scala",
    "Shell": "Bash scripting",
    "HCL": "Terraform",
    "Dockerfile": "Docker",
    "YAML": "YAML",
    "SQL": "SQL",
    "HTML": "HTML",
    "CSS": "CSS",
}

# Topic → skill label
TOPIC_SKILL_MAP: dict[str, str] = {
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "terraform": "Terraform",
    "aws": "Amazon Web Services",
    "gcp": "Google Cloud Platform",
    "azure": "Microsoft Azure",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "react": "React",
    "nextjs": "Next.js",
    "vue": "Vue.js",
    "angular": "Angular",
    "graphql": "GraphQL",
    "postgresql": "PostgreSQL",
    "redis": "Redis",
    "kafka": "Apache Kafka",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "mlops": "MLOps",
    "ci-cd": "CI/CD",
    "microservices": "Microservices",
}


def infer_skills_from_repos(repos: list[dict], languages_per_repo: dict[str, dict]) -> list[dict]:
    """
    Aggregate language bytes across all repos, then convert to skill signals.
    Returns list of dicts compatible with SkillDTO.
    """
    total_bytes: dict[str, int] = {}
    all_topics: set[str] = set()

    for repo in repos:
        repo_name = repo.get("full_name", "")
        langs = languages_per_repo.get(repo_name, {})
        for lang, byte_count in langs.items():
            total_bytes[lang] = total_bytes.get(lang, 0) + byte_count

        for topic in repo.get("topics", []):
            all_topics.add(topic.lower())

    grand_total = sum(total_bytes.values()) or 1
    skills: list[dict] = []

    # Language-based skills
    for lang, byte_count in total_bytes.items():
        label = LANGUAGE_SKILL_MAP.get(lang, lang)
        pct = byte_count / grand_total
        confidence = min(0.95, 0.3 + pct * 2)  # 30% base, scales with code volume
        nivel = _infer_nivel(pct)

        skills.append({
            "raw_label": lang,
            "esco_uri": None,
            "esco_label": label,
            "nivel": nivel,
            "confidence_score": round(confidence, 2),
            "source": "github",
            "evidence": {"bytes": byte_count, "pct_of_total": round(pct * 100, 1)},
        })

    # Topic-based skills
    for topic in all_topics:
        if topic in TOPIC_SKILL_MAP:
            skills.append({
                "raw_label": topic,
                "esco_uri": None,
                "esco_label": TOPIC_SKILL_MAP[topic],
                "nivel": None,
                "confidence_score": 0.6,
                "source": "github",
                "evidence": {"from": "repo_topic"},
            })

    return skills


def _infer_nivel(pct_of_total: float) -> str:
    if pct_of_total >= 0.4:
        return "senior"
    elif pct_of_total >= 0.15:
        return "mid"
    return "junior"
