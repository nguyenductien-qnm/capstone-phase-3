import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add recommendation module to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.modules['openfeature.contrib.hook.opentelemetry'] = MagicMock()
sys.modules['openfeature.contrib.hook'] = MagicMock()
sys.modules['openfeature.contrib.provider'] = MagicMock()
sys.modules['openfeature.contrib.provider.flagd'] = MagicMock()
sys.modules['openfeature.contrib'] = MagicMock()
sys.modules['psycopg2'] = MagicMock()
sys.modules['psycopg2.extensions'] = MagicMock()
sys.modules['pgvector'] = MagicMock()
sys.modules['pgvector.psycopg2'] = MagicMock()
sys.modules['grpc_health'] = MagicMock()
sys.modules['grpc_health.v1'] = MagicMock()
sys.modules['demo_pb2'] = MagicMock()
sys.modules['demo_pb2_grpc'] = MagicMock()
import recommendation_server

class TestRecommendationServer(unittest.TestCase):
    @patch('recommendation_server.psycopg2.connect')
    @patch('recommendation_server.register_vector')
    def test_get_recommendations(self, mock_register_vector, mock_connect):
        # Setup mock connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_cursor.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # First fetchone() returns the embedding vector for the source product
        mock_cursor.fetchone.return_value = ([0.1, 0.2, 0.3],)

        # Second fetchall() returns 5 similar product IDs
        mock_cursor.fetchall.return_value = [("p1",), ("p2",), ("p3",), ("p4",), ("p5",)]

        # Call the actual method being tested
        with patch.dict(os.environ, {'DB_CONNECTION_STRING': 'postgresql://dummy:dummy@localhost:5432/dummy'}):
            try:
                results = recommendation_server._get_ai_recommendations(["source_product"], max_results=5)
                
                # Assertions
                self.assertEqual(len(results), 5)
                self.assertEqual(results[0], "p1")
                
                # Check if pgvector <=> distance was used in the query
                query_calls = mock_cursor.execute.call_args_list
                self.assertTrue(len(query_calls) >= 2)
                second_query = query_calls[1][0][0].lower()
                self.assertTrue("<=>" in second_query)
                
                print("✅ PASSED: Recommendation pgvector logic is correct.")
            except Exception as e:
                print(f"❌ FAILED: {e}")
                sys.exit(1)

if __name__ == '__main__':
    unittest.main()
