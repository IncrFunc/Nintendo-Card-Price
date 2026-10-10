from nsg_price.mogushijian import CATALOG_URL, fetch_catalog


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        page = kwargs["json"]["page"]
        if page == 1:
            return FakeResponse({"hasMore": True, "next": 2, "list": [{"cardsId": 1, "name": "A"}]})
        return FakeResponse({"hasMore": False, "next": None, "list": [{"cardsId": 2, "name": "B"}]})


def test_fetch_catalog_follows_public_api_pagination():
    session = FakeSession()

    rows = fetch_catalog(session, timeout=7, retries=0)

    assert [row["cardsId"] for row in rows] == [1, 2]
    assert [call[0] for call in session.calls] == [CATALOG_URL, CATALOG_URL]
    assert [call[1]["json"] for call in session.calls] == [{"page": 1}, {"page": 2}]
    assert all(call[1]["headers"]["alianame"] == "alia2" for call in session.calls)
