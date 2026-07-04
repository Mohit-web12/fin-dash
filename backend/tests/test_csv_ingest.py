import io


def upload(client, auth_headers, content: str, filename="upload.csv"):
    return client.post(
        "/ingest/csv",
        files={"file": (filename, io.BytesIO(content.encode()), "text/csv")},
        headers=auth_headers,
    )


def test_ingest_basic_csv(client, auth_headers):
    csv = (
        "date,amount,merchant\n"
        "2026-01-01,-12.34,Starbucks\n"
        "2026-01-02,-45.67,Uber\n"
    )
    resp = upload(client, auth_headers, csv)
    assert resp.status_code == 200
    body = resp.json()
    assert body["inserted"] == 2
    assert body["skipped_duplicates"] == 0
    assert body["skipped_errors"] == 0

    rows = client.get("/transactions", headers=auth_headers).json()
    assert len(rows) == 2


def test_ingest_uses_provided_category(client, auth_headers):
    csv = "date,amount,merchant,category,subcategory\n2026-01-01,-12.34,Starbucks,Custom Cat,Custom Sub\n"
    upload(client, auth_headers, csv)
    rows = client.get("/transactions", headers=auth_headers).json()
    assert rows[0]["category"] == "Custom Cat"
    assert rows[0]["subcategory"] == "Custom Sub"


def test_ingest_falls_back_to_auto_categorize_without_category_column(client, auth_headers):
    csv = "date,amount,merchant\n2026-01-01,-12.34,Starbucks\n"
    upload(client, auth_headers, csv)
    rows = client.get("/transactions", headers=auth_headers).json()
    assert rows[0]["category"] == "Dining"


def test_ingest_missing_amount_column_returns_400_not_500(client, auth_headers):
    csv = "date,merchant\n2026-01-01,Test\n"
    resp = upload(client, auth_headers, csv)
    assert resp.status_code == 400
    assert "amount" in resp.json()["detail"]


def test_ingest_missing_date_column_returns_400_not_500(client, auth_headers):
    csv = "amount,merchant\n-12.34,Test\n"
    resp = upload(client, auth_headers, csv)
    assert resp.status_code == 400
    assert "date" in resp.json()["detail"]


def test_ingest_bad_amount_value_is_skipped_not_500(client, auth_headers):
    csv = (
        "date,amount,merchant\n"
        "2026-01-01,abc,BadRow\n"
        "2026-01-02,-5.00,GoodRow\n"
    )
    resp = upload(client, auth_headers, csv)
    assert resp.status_code == 200
    body = resp.json()
    assert body["inserted"] == 1
    assert body["skipped_errors"] == 1
    assert body["errors"][0]["row"] == 2
    assert "amount" in body["errors"][0]["reason"]


def test_ingest_bad_date_value_is_skipped_not_500(client, auth_headers):
    csv = (
        "date,amount,merchant\n"
        "not-a-date,-5.00,BadRow\n"
        "2026-01-02,-5.00,GoodRow\n"
    )
    resp = upload(client, auth_headers, csv)
    assert resp.status_code == 200
    body = resp.json()
    assert body["inserted"] == 1
    assert body["skipped_errors"] == 1


def test_ingest_dedupes_against_existing_transactions(client, auth_headers):
    csv = "date,amount,merchant\n2026-01-01,-12.34,Starbucks\n"
    first = upload(client, auth_headers, csv)
    assert first.json()["inserted"] == 1

    second = upload(client, auth_headers, csv)
    body = second.json()
    assert body["inserted"] == 0
    assert body["skipped_duplicates"] == 1

    rows = client.get("/transactions", headers=auth_headers).json()
    assert len(rows) == 1


def test_ingest_dedupes_within_same_batch(client, auth_headers):
    csv = (
        "date,amount,merchant\n"
        "2026-01-01,-12.34,Starbucks\n"
        "2026-01-01,-12.34,Starbucks\n"
    )
    resp = upload(client, auth_headers, csv)
    body = resp.json()
    assert body["inserted"] == 1
    assert body["skipped_duplicates"] == 1


def test_ingest_completely_unparseable_file(client, auth_headers):
    resp = upload(client, auth_headers, "", filename="empty.csv")
    assert resp.status_code == 400


def test_ingest_requires_auth(client):
    resp = client.post(
        "/ingest/csv",
        files={"file": ("x.csv", io.BytesIO(b"date,amount\n2026-01-01,-1\n"), "text/csv")},
    )
    assert resp.status_code == 401
