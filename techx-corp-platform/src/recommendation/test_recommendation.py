import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
for module in (
    'openfeature.contrib.hook.opentelemetry', 'openfeature.contrib.hook',
    'openfeature.contrib.provider', 'openfeature.contrib.provider.flagd',
    'openfeature.contrib', 'psycopg2', 'psycopg2.pool',
    'psycopg2.extensions', 'pgvector', 'pgvector.psycopg2',
    'grpc_health', 'grpc_health.v1', 'demo_pb2', 'demo_pb2_grpc',
):
    sys.modules[module] = MagicMock()

import recommendation_server


class NumpyLikeFloat:
    def __init__(self, value):
        self.value = value

    def __float__(self):
        return self.value

    def __repr__(self):
        return f"np.float32({self.value})"


class TestRecommendationServer(unittest.TestCase):
    def test_get_recommendations_serializes_pgvector_values_as_plain_floats(self):
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.fetchone.return_value = ([NumpyLikeFloat(0.1), NumpyLikeFloat(0.2)],)
        cursor.fetchall.return_value = [("p1",), ("p2",)]

        connection = MagicMock()
        connection.cursor.return_value = cursor
        pool = MagicMock()
        pool.getconn.return_value = connection
        tracer = MagicMock()
        tracer.start_as_current_span.return_value.__enter__.return_value = MagicMock()

        with patch.object(recommendation_server, 'tracer', tracer, create=True), \
             patch.object(recommendation_server, 'get_db_pool', return_value=pool), \
             patch.object(recommendation_server, 'register_vector'), \
             patch.object(recommendation_server, '_get_random_recommendations') as fallback:
            results = recommendation_server._get_ai_recommendations(["source_product"], max_results=2)

        self.assertEqual(results, ["p1", "p2"])
        fallback.assert_not_called()
        second_query_params = cursor.execute.call_args_list[1].args[1]
        self.assertEqual(second_query_params[1], "[0.1, 0.2]")
        pool.putconn.assert_called_once_with(connection, close=False)


if __name__ == '__main__':
    unittest.main()
