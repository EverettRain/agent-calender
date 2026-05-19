from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest


def _iso_future(hours: int = 24) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


# ===== Tag CRUD =====


@pytest.mark.asyncio
async def test_tag_crud_basic(client):
    # Create
    r = await client.post("/tags", json={"name": "work", "color": "#3b82f6"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "work"
    assert body["color"] == "#3b82f6"
    tag_id = body["id"]

    # List
    r = await client.get("/tags")
    assert r.status_code == 200
    assert any(t["id"] == tag_id for t in r.json())

    # Update name + color
    r = await client.put(
        f"/tags/{tag_id}",
        json={"name": "WORK", "color": "#10b981"},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "WORK"
    assert r.json()["color"] == "#10b981"

    # Delete
    r = await client.delete(f"/tags/{tag_id}")
    assert r.status_code == 204
    r = await client.get("/tags")
    assert not any(t["id"] == tag_id for t in r.json())


@pytest.mark.asyncio
async def test_tag_duplicate_name_409(client):
    await client.post("/tags", json={"name": "personal"})
    r = await client.post("/tags", json={"name": "personal"})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_tag_invalid_color_422(client):
    r = await client.post("/tags", json={"name": "x", "color": "not-hex"})
    assert r.status_code == 422


# ===== Group CRUD =====


@pytest.mark.asyncio
async def test_group_crud_basic(client):
    r = await client.post("/groups", json={"name": "Work", "position": 1})
    assert r.status_code == 201
    gid = r.json()["id"]

    r = await client.get("/groups")
    assert any(g["id"] == gid for g in r.json())

    r = await client.put(f"/groups/{gid}", json={"name": "Work++", "position": 2})
    assert r.status_code == 200
    assert r.json()["name"] == "Work++"
    assert r.json()["position"] == 2

    r = await client.delete(f"/groups/{gid}")
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_group_duplicate_name_409(client):
    await client.post("/groups", json={"name": "G1"})
    r = await client.post("/groups", json={"name": "G1"})
    assert r.status_code == 409


# ===== Reminder with tags/group =====


@pytest.mark.asyncio
async def test_create_reminder_with_tags_and_group(client):
    t1 = (await client.post("/tags", json={"name": "code"})).json()
    t2 = (await client.post("/tags", json={"name": "review"})).json()
    g = (await client.post("/groups", json={"name": "Engineering"})).json()

    r = await client.post(
        "/reminders",
        json={
            "kind": "event",
            "title": "code review",
            "target_at": _iso_future(),
            "group_id": g["id"],
            "tag_ids": [t1["id"], t2["id"]],
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["group_id"] == g["id"]
    assert {t["name"] for t in body["tags"]} == {"code", "review"}


@pytest.mark.asyncio
async def test_update_reminder_change_tags(client):
    t1 = (await client.post("/tags", json={"name": "a"})).json()
    t2 = (await client.post("/tags", json={"name": "b"})).json()
    t3 = (await client.post("/tags", json={"name": "c"})).json()

    created = await client.post(
        "/reminders",
        json={
            "kind": "event",
            "title": "x",
            "target_at": _iso_future(),
            "tag_ids": [t1["id"], t2["id"]],
        },
    )
    rid = created.json()["id"]

    # Replace tags with just t3
    r = await client.put(f"/reminders/{rid}", json={"tag_ids": [t3["id"]]})
    assert r.status_code == 200
    assert {t["name"] for t in r.json()["tags"]} == {"c"}

    # Clear all tags with []
    r = await client.put(f"/reminders/{rid}", json={"tag_ids": []})
    assert r.status_code == 200
    assert r.json()["tags"] == []


@pytest.mark.asyncio
async def test_delete_group_clears_reminder_group_id(client):
    g = (await client.post("/groups", json={"name": "Temp"})).json()
    created = await client.post(
        "/reminders",
        json={
            "kind": "event",
            "title": "x",
            "target_at": _iso_future(),
            "group_id": g["id"],
        },
    )
    rid = created.json()["id"]
    assert created.json()["group_id"] == g["id"]

    # Delete the group → reminder's group_id should become None
    r = await client.delete(f"/groups/{g['id']}")
    assert r.status_code == 204

    r = await client.get(f"/reminders/{rid}")
    assert r.status_code == 200
    assert r.json()["group_id"] is None


@pytest.mark.asyncio
async def test_delete_tag_removes_association(client):
    t = (await client.post("/tags", json={"name": "x"})).json()
    created = await client.post(
        "/reminders",
        json={
            "kind": "event",
            "title": "x",
            "target_at": _iso_future(),
            "tag_ids": [t["id"]],
        },
    )
    rid = created.json()["id"]
    assert len(created.json()["tags"]) == 1

    r = await client.delete(f"/tags/{t['id']}")
    assert r.status_code == 204

    r = await client.get(f"/reminders/{rid}")
    assert r.status_code == 200
    assert r.json()["tags"] == []


@pytest.mark.asyncio
async def test_list_filters_by_group_and_tag(client, stub_llm):
    # Create one ingest-created reminder (has no group, no tags)
    stub_llm.push(
        json.dumps(
            {"reminders": [{"kind": "event", "title": "ingested", "target_at": _iso_future()}]}
        )
    )
    stub_llm.push(json.dumps({"pass": True, "issues": []}))
    await client.post("/ingest", json={"text": "原文"})

    # Create one manual reminder in a group with a tag
    t = (await client.post("/tags", json={"name": "prj"})).json()
    g = (await client.post("/groups", json={"name": "Prj"})).json()
    await client.post(
        "/reminders",
        json={
            "kind": "event",
            "title": "in-group",
            "target_at": _iso_future(),
            "group_id": g["id"],
            "tag_ids": [t["id"]],
        },
    )

    # Filter by group_id
    r = await client.get(f"/reminders?group_id={g['id']}")
    assert r.status_code == 200
    titles = [x["title"] for x in r.json()]
    assert titles == ["in-group"]

    # Filter by inbox (no group)
    r = await client.get("/reminders?group_id=__inbox__")
    titles = [x["title"] for x in r.json()]
    assert "ingested" in titles
    assert "in-group" not in titles

    # Filter by tag
    r = await client.get(f"/reminders?tag_id={t['id']}")
    titles = [x["title"] for x in r.json()]
    assert titles == ["in-group"]


@pytest.mark.asyncio
async def test_list_excludes_cancelled_by_default(client):
    # Create one, then delete it
    created = await client.post(
        "/reminders",
        json={"kind": "event", "title": "doomed", "target_at": _iso_future()},
    )
    rid = created.json()["id"]
    await client.delete(f"/reminders/{rid}")

    # Default list: doomed not in results
    r = await client.get("/reminders")
    assert all(x["title"] != "doomed" for x in r.json())

    # include_cancelled=true: doomed is in results
    r = await client.get("/reminders?include_cancelled=true")
    assert any(x["title"] == "doomed" for x in r.json())


@pytest.mark.asyncio
async def test_create_reminder_unknown_group_id_422(client):
    r = await client.post(
        "/reminders",
        json={
            "kind": "event",
            "title": "x",
            "target_at": _iso_future(),
            "group_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_reminder_unknown_tag_id_422(client):
    r = await client.post(
        "/reminders",
        json={
            "kind": "event",
            "title": "x",
            "target_at": _iso_future(),
            "tag_ids": ["00000000-0000-0000-0000-000000000000"],
        },
    )
    assert r.status_code == 422
