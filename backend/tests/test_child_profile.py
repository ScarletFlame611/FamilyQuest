import pytest
from httpx import AsyncClient
from sqlalchemy import inspect, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.families.models import Member
from app.seed import DemoFamily
from tests.api import adult_token, bearer, child_token

pytestmark = [pytest.mark.anyio, pytest.mark.us04]

LIZA = {"name": "Лиза", "avatar": "fox", "age_group": "8-10", "parent_consent": True}


async def test_adult_creates_child_profile(client: AsyncClient, demo: DemoFamily):
    mama = await adult_token(client)
    created = await client.post("/api/family/children", json=LIZA, headers=bearer(mama))
    assert created.status_code == 201
    child = created.json()
    assert (child["name"], child["role"], child["age_group"]) == ("Лиза", "child", "8-10")
    family = (await client.get("/api/family", headers=bearer(mama))).json()
    assert child["id"] in [m["id"] for m in family["members"]]


async def test_profile_is_not_created_without_consent(client: AsyncClient, demo: DemoFamily):
    mama = await adult_token(client)
    refused = await client.post(
        "/api/family/children", json={**LIZA, "parent_consent": False}, headers=bearer(mama)
    )
    assert refused.status_code == 422
    assert refused.json()["detail"] == "Без согласия взрослого профиль ребёнка не создаётся"
    missing = {k: v for k, v in LIZA.items() if k != "parent_consent"}
    no_field = await client.post("/api/family/children", json=missing, headers=bearer(mama))
    assert no_field.status_code == 422
    family = (await client.get("/api/family", headers=bearer(mama))).json()
    assert "Лиза" not in [m["name"] for m in family["members"]]


@pytest.mark.parametrize("age_group", ["5-6", "14-16", "", None])
async def test_only_three_age_groups(client: AsyncClient, demo: DemoFamily, age_group):
    mama = await adult_token(client)
    response = await client.post(
        "/api/family/children", json={**LIZA, "age_group": age_group}, headers=bearer(mama)
    )
    assert response.status_code == 422


async def test_child_cannot_add_children(client: AsyncClient, demo: DemoFamily):
    masha = await child_token(client, demo.masha_id)
    response = await client.post("/api/family/children", json=LIZA, headers=bearer(masha))
    assert response.status_code == 403


async def test_profile_has_no_email_phone_or_birth_date(client: AsyncClient, session):
    columns = set(
        await session.run_sync(
            lambda s: [c["name"] for c in inspect(s.connection()).get_columns("members")]
        )
    )
    assert not [c for c in columns if any(w in c for w in ("mail", "phone", "birth"))]
    spec = (await client.get("/api/openapi.json")).json()["components"]["schemas"]
    assert set(spec["ChildCreateIn"]["properties"]) == {
        "name",
        "avatar",
        "age_group",
        "parent_consent",
    }
    assert set(spec["MemberOut"]["properties"]) == {"id", "name", "role", "avatar", "age_group"}


async def test_database_rejects_child_without_consent(session: AsyncSession, demo: DemoFamily):
    child = await session.scalar(select(Member).where(Member.id == demo.masha_id))
    assert child is not None
    assert child.parent_consent_at is not None
    with pytest.raises(IntegrityError, match="ck_members_child_profile_complete"):
        await session.execute(
            update(Member).where(Member.id == demo.masha_id).values(parent_consent_at=None)
        )
