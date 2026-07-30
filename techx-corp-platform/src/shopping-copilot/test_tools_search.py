import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import tools


class _Channel:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class SearchProductsTest(unittest.TestCase):
    def test_retries_broad_category_when_specific_query_returns_nothing(self):
        product = SimpleNamespace(
            id="p1", name="Starter Scope",
            price_usd=SimpleNamespace(units=99, nanos=0),
            categories=["telescopes"], description="beginner telescope",
        )

        class Stub:
            queries = []

            def SearchProducts(self, request, timeout):
                self.queries.append(request.query)
                return SimpleNamespace(results=[] if len(self.queries) == 1 else [product])

        stub = Stub()
        with patch.object(tools.grpc, "insecure_channel", return_value=_Channel()), \
             patch.object(tools.demo_pb2_grpc, "ProductCatalogServiceStub", return_value=stub):
            result = json.loads(tools.search_products("beginner stargazing", "Telescopes"))

        self.assertEqual(stub.queries, ["beginner stargazing", "Telescopes"])
        self.assertEqual(result["products"][0]["name"], "Starter Scope")


if __name__ == "__main__":
    unittest.main()
