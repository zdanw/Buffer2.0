"""List prompt-dimensions must not N+1 remote compat tables."""

from sqlalchemy import event

from bebcare.database import engine
from conftest import register_or_create_user


def _count_sql(run):
    n = {"q": 0}

    def _before(*_args, **_kwargs):
        n["q"] += 1

    event.listen(engine, "before_cursor_execute", _before)
    try:
        run()
    finally:
        event.remove(engine, "before_cursor_execute", _before)
    return n["q"]


def _seed_dims_with_compat(client, headers, n: int, product_type: str):
    ids = []
    for i in range(n):
        resp = client.post(
            "/v1/prompt-dimensions/",
            headers=headers,
            json={
                "product_type": product_type,
                "dimension_type": "scenes",
                "name": f"Scene {i}",
                "compatibilities": {
                    "styles": {"mode": "allowlist", "items": [f"style-{i}"]},
                },
            },
        )
        assert resp.status_code == 201, resp.text
        ids.append(resp.json()["dimension_id"])
    return ids


def test_list_prompt_dimensions_sql_does_not_scale_with_page_size(
    full_client, auth_headers
):
    n = 12
    product_type = "nplus1_list"
    headers = register_or_create_user(
        full_client,
        auth_headers,
        "perf_pd_nplus1",
        "perf_pd_nplus1@test.local",
        "PassNplus1123!",
    )
    _seed_dims_with_compat(full_client, headers, n, product_type)

    captured = {}

    def _get():
        resp = full_client.get(
            f"/v1/prompt-dimensions/?product_type={product_type}&page_size={n}",
            headers=headers,
        )
        captured["resp"] = resp

    queries = _count_sql(_get)
    resp = captured["resp"]
    assert resp.status_code == 200, resp.text
    rows = resp.json()["data"]
    assert len(rows) == n
    assert rows[0]["compatibilities"]["styles"]["mode"] == "allowlist"
    # count + page + 2 selectinloads + auth lookup; must not be ~2N lazy loads
    assert queries < n, f"list issued {queries} SQL statements for {n} rows"


def test_list_prompt_dimensions_can_omit_compat_payload(
    full_client, auth_headers
):
    n = 8
    product_type = "nplus1_lite"
    headers = register_or_create_user(
        full_client,
        auth_headers,
        "perf_pd_lite",
        "perf_pd_lite@test.local",
        "PassLite1234!",
    )
    _seed_dims_with_compat(full_client, headers, n, product_type)

    captured = {}

    def _get():
        resp = full_client.get(
            f"/v1/prompt-dimensions/?product_type={product_type}"
            f"&page_size={n}&include_compat=false",
            headers=headers,
        )
        captured["resp"] = resp

    queries = _count_sql(_get)
    resp = captured["resp"]
    assert resp.status_code == 200, resp.text
    rows = resp.json()["data"]
    assert len(rows) == n
    for row in rows:
        styles = (row.get("compatibilities") or {}).get("styles") or {}
        assert styles.get("mode", "unrestricted") == "unrestricted"
        assert styles.get("items", []) == []
    assert queries < n, f"lite list issued {queries} SQL statements for {n} rows"
