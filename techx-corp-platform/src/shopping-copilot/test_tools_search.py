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
    def test_filters_secondary_category_accessories_and_budget(self):
        accessory = SimpleNamespace(
            id="a1", name="Solar Filter",
            price_usd=SimpleNamespace(units=69, nanos=0),
            categories=["accessories", "telescopes"], description="filter for a telescope",
        )
        affordable_scope = SimpleNamespace(
            id="t1", name="Starter Scope",
            price_usd=SimpleNamespace(units=129, nanos=0),
            categories=["telescopes", "travel"], description="beginner telescope",
        )
        expensive_scope = SimpleNamespace(
            id="t2", name="Pro Scope",
            price_usd=SimpleNamespace(units=349, nanos=0),
            categories=["telescopes"], description="advanced telescope",
        )

        class Stub:
            def SearchProducts(self, request, timeout):
                return SimpleNamespace(results=[accessory, affordable_scope, expensive_scope])

        with patch.object(tools.grpc, "insecure_channel", return_value=_Channel()), \
             patch.object(tools.demo_pb2_grpc, "ProductCatalogServiceStub", return_value=Stub()):
            result = json.loads(tools.search_products("beginner telescope under $200", "Telescopes"))

        self.assertEqual([p["name"] for p in result["products"]], ["Starter Scope"])

    def test_falls_back_to_catalog_name_matching_for_eval_compare(self):
        national_park = SimpleNamespace(
            id="n1", name="National Park Foundation Explorascope",
            price_usd=SimpleNamespace(units=89, nanos=0),
            categories=["telescopes"], description="starter telescope",
        )
        roof = SimpleNamespace(
            id="b1", name="Roof Binoculars",
            price_usd=SimpleNamespace(units=49, nanos=0),
            categories=["binoculars"], description="compact binoculars",
        )

        class Stub:
            def SearchProducts(self, request, timeout):
                return SimpleNamespace(results=[])

            def ListProducts(self, request, timeout):
                return SimpleNamespace(products=[national_park, roof])

        with patch.object(tools.grpc, "insecure_channel", return_value=_Channel()), \
             patch.object(tools.demo_pb2_grpc, "ProductCatalogServiceStub", return_value=Stub()):
            result = json.loads(tools.search_products("Kính thiên văn National Park"))

        self.assertEqual([p["name"] for p in result["products"]], ["National Park Foundation Explorascope"])

    def test_vietnamese_telescope_query_uses_catalog_category_hint(self):
        telescope = SimpleNamespace(
            id="t1", name="Starter Scope",
            price_usd=SimpleNamespace(units=129, nanos=0),
            categories=["telescopes", "travel"], description="beginner telescope",
        )

        class Stub:
            def SearchProducts(self, request, timeout):
                return SimpleNamespace(results=[])

            def ListProducts(self, request, timeout):
                return SimpleNamespace(products=[telescope])

        with patch.object(tools.grpc, "insecure_channel", return_value=_Channel()), \
             patch.object(tools.demo_pb2_grpc, "ProductCatalogServiceStub", return_value=Stub()):
            result = json.loads(tools.search_products("kính viễn vọng"))

        self.assertEqual([p["name"] for p in result["products"]], ["Starter Scope"])

    def test_category_fallback_uses_primary_category_from_full_catalog(self):
        accessory = SimpleNamespace(
            id="a1", name="Solar Filter",
            price_usd=SimpleNamespace(units=69, nanos=0),
            categories=["accessories", "telescopes"], description="filter",
        )
        telescope = SimpleNamespace(
            id="t1", name="Starter Scope",
            price_usd=SimpleNamespace(units=129, nanos=0),
            categories=["telescopes", "travel"], description="beginner telescope",
        )

        class Stub:
            def SearchProducts(self, request, timeout):
                return SimpleNamespace(results=[accessory])

            def ListProducts(self, request, timeout):
                return SimpleNamespace(products=[accessory, telescope])

        with patch.object(tools.grpc, "insecure_channel", return_value=_Channel()), \
             patch.object(tools.demo_pb2_grpc, "ProductCatalogServiceStub", return_value=Stub()):
            result = json.loads(tools.search_products("kính viễn vọng", "Telescopes"))

        self.assertEqual([p["name"] for p in result["products"]], ["Starter Scope"])

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

class OperationalToolsTest(unittest.TestCase):
    def test_nonzero_currency_conversion_rejects_zero_service_result(self):
        class Stub:
            def Convert(self, request, timeout):
                return SimpleNamespace(units=0, nanos=0)

        with patch.object(tools.grpc, "insecure_channel", return_value=_Channel()), \
             patch.object(tools.demo_pb2_grpc, "CurrencyServiceStub", return_value=Stub()):
            result = json.loads(tools.convert_currency(500, "USD", "VND"))

        self.assertIn("error", result)
        self.assertIn("unavailable", result["error"].lower())

    def test_shipping_quote_uses_http_and_includes_groundable_amount(self):
        captured = []

        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self):
                return json.dumps({"cost_usd": {"currency_code": "USD", "units": 8, "nanos": 990000000}}).encode("utf-8")

        def urlopen(request, timeout):
            captured.append(json.loads(request.data.decode("utf-8")))
            return Response()

        with patch.object(tools.urllib.request, "urlopen", side_effect=urlopen):
            result = json.loads(tools.get_shipping_quote(address={"city": "Hanoi"}))

        self.assertEqual(result["formatted_cost"], "$8.99 USD")
        self.assertEqual(captured[0]["address"]["city"], "Hanoi")
        self.assertEqual(captured[0]["items"][0]["product_id"], "OLJCESPC7Z")


def test_recommendations_include_catalog_names_for_grounding():
    class RecommendationStub:
        def ListRecommendations(self, request, timeout):
            return SimpleNamespace(product_ids=["a1", "a2"])

    class CatalogStub:
        def ListProducts(self, request, timeout):
            return SimpleNamespace(products=[
                SimpleNamespace(id="a1", name="Solar Filter", price_usd=SimpleNamespace(units=69, nanos=0), categories=["accessories"], description="Protective solar viewing filter"),
                SimpleNamespace(id="a2", name="Red Flashlight", price_usd=SimpleNamespace(units=19, nanos=0), categories=["accessories"], description="Preserves night vision"),
            ])

    with patch.object(tools.demo_pb2_grpc, "RecommendationServiceStub", return_value=RecommendationStub()), \
         patch.object(tools.demo_pb2_grpc, "ProductCatalogServiceStub", return_value=CatalogStub()), \
         patch.object(tools.grpc, "insecure_channel", return_value=_Channel()):
        result = json.loads(tools.list_recommendations(["scope-1"]))

    assert [p["name"] for p in result["recommended_products"]] == ["Solar Filter", "Red Flashlight"]
