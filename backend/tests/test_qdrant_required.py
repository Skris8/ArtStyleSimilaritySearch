"""Pruebas del contrato obligatorio entre el catálogo y Qdrant."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from backend import app as backend_app


class EmptyQdrantClient:
    def scroll(self, **_kwargs):
        return [], None

    def retrieve(self, **_kwargs):
        return []

    def query_points(self, **_kwargs):
        return []


class NoNeighborsQdrantClient(EmptyQdrantClient):
    def retrieve(self, **_kwargs):
        return [{'id': '1', 'payload': {}, 'vector': None}]


class FailingQdrantClient:
    def __getattr__(self, _name):
        def fail(**_kwargs):
            raise ConnectionError('Qdrant unavailable')

        return fail


class TypePayloadQdrantClient:
    def __init__(self):
        self.scroll_kwargs = None

    def scroll(self, **kwargs):
        self.scroll_kwargs = kwargs
        return [SimpleNamespace(payload={'type': 'anime'})], None


class QueryFailureWithSourceClient:
    def __init__(self):
        self.retrieve_kwargs = None

    def query_points(self, **_kwargs):
        raise TimeoutError('Similarity query timed out')

    def retrieve(self, **kwargs):
        self.retrieve_kwargs = kwargs
        return [SimpleNamespace(id=0, payload=None, vector=[0.1, 0.2])]


class VectorFallbackClient(QueryFailureWithSourceClient):
    def query_points(self, **kwargs):
        query = kwargs['query']
        if not isinstance(query, list):
            raise TimeoutError('Query by id timed out')
        return SimpleNamespace(points=[
            SimpleNamespace(id=0, score=1.0, payload={'type': 'anime'}),
            SimpleNamespace(id=8, score=0.98, payload={'type': 'anime'}),
            SimpleNamespace(id=9, score=0.97, payload={'type': 'anime'}),
        ])


class CatalogFilterClient:
    def __init__(self):
        self.scroll_calls = []
        self.retrieve_calls = []
        self.points = [
            SimpleNamespace(id=0, payload={'title': 'Café nocturno', 'type': 'anime', 'resolution': '10 × 10'}),
            SimpleNamespace(id=1, payload={'title': 'Ciudad', 'type': 'cyberpunk', 'resolution': '20 × 20'}),
            SimpleNamespace(id=2, payload={'title': 'Bosque', 'type': 'anime', 'resolution': '30 × 30'}),
        ]

    def scroll(self, **kwargs):
        self.scroll_calls.append(kwargs)
        return self.points, None

    def retrieve(self, **kwargs):
        self.retrieve_calls.append(kwargs)
        requested = {str(rid) for rid in kwargs['ids']}
        return [point for point in self.points if str(point.id) in requested]


class StyleSimilarityClient:
    def __init__(self):
        self.query_kwargs = None
        self.retrieve_calls = []
        self.points = [
            SimpleNamespace(id=0, score=1.0, payload={'type': 'anime'}, vector=[0.1, 0.2]),
            SimpleNamespace(id=1, score=0.99, payload={'type': 'cyberpunk'}, vector=None),
            SimpleNamespace(id=2, score=0.98, payload={'type': 'anime'}, vector=None),
            SimpleNamespace(id=3, score=0.97, payload={'type': 'cyberpunk'}, vector=None),
            SimpleNamespace(id=4, score=0.96, payload={'type': 'anime'}, vector=None),
        ]

    def count(self, **_kwargs):
        return SimpleNamespace(count=len(self.points))

    def query_points(self, **kwargs):
        self.query_kwargs = kwargs
        return SimpleNamespace(points=self.points)

    def retrieve(self, **kwargs):
        self.retrieve_calls.append(kwargs)
        requested = {str(rid) for rid in kwargs['ids']}
        return [point for point in self.points if str(point.id) in requested]


class QdrantRequiredTests(unittest.TestCase):
    """Comprueba errores, filtros, orden y compatibilidad de respuestas."""

    def assert_http_error(self, expected_status, operation):
        with self.assertRaises(HTTPException) as raised:
            operation()
        self.assertEqual(expected_status, raised.exception.status_code)

    @patch.object(backend_app, '_get_qdrant_client', return_value=None)
    def test_missing_client_returns_503_without_local_fallback(self, _client):
        self.assert_http_error(503, backend_app.get_types)
        self.assert_http_error(503, backend_app.get_records)
        self.assert_http_error(503, lambda: backend_app.get_similar('1'))

    @patch.object(backend_app, '_get_qdrant_client', return_value=FailingQdrantClient())
    def test_connection_errors_return_503_without_local_fallback(self, _client):
        self.assert_http_error(503, backend_app.get_types)
        self.assert_http_error(503, backend_app.get_records)
        self.assert_http_error(503, lambda: backend_app.get_similar('1'))

    @patch.object(backend_app, '_get_qdrant_client', return_value=EmptyQdrantClient())
    def test_successful_empty_catalog_returns_empty_lists(self, _client):
        self.assertEqual([], backend_app.get_types())
        self.assertEqual([], backend_app.get_records())

    @patch.object(backend_app, '_get_qdrant_client', return_value=EmptyQdrantClient())
    def test_missing_similarity_source_returns_404(self, _client):
        self.assert_http_error(404, lambda: backend_app.get_similar('missing'))

    @patch.object(backend_app, '_get_qdrant_client', return_value=NoNeighborsQdrantClient())
    def test_valid_similarity_without_neighbors_returns_empty_list(self, _client):
        self.assertEqual([], backend_app.get_similar('1'))

    def test_source_retrieval_does_not_turn_failed_queries_into_empty_success(self):
        client = QueryFailureWithSourceClient()
        with patch.object(backend_app, '_get_qdrant_client', return_value=client):
            self.assert_http_error(503, lambda: backend_app.get_similar('0'))
        self.assertFalse(client.retrieve_kwargs['with_payload'])
        self.assertTrue(client.retrieve_kwargs['with_vectors'])

    def test_failed_id_query_retries_with_source_vector(self):
        client = VectorFallbackClient()
        with patch.object(backend_app, '_get_qdrant_client', return_value=client):
            records = backend_app.get_similar('0', limit=2)
        self.assertEqual([8, 9], [record['id'] for record in records])
        self.assertEqual([0.98, 0.97], [record['score'] for record in records])

    def test_strict_similarity_still_rejects_incomplete_results(self):
        client = VectorFallbackClient()
        with patch.object(backend_app, '_get_qdrant_client', return_value=client):
            self.assert_http_error(
                500,
                lambda: backend_app._get_qdrant_similar_records('0', limit=12, strict=True)
            )

    def test_types_request_excludes_image_payloads_and_vectors(self):
        client = TypePayloadQdrantClient()
        with patch.object(backend_app, '_get_qdrant_client', return_value=client):
            self.assertEqual(['anime'], backend_app.get_types())
        self.assertEqual(['type'], client.scroll_kwargs['with_payload'])
        self.assertFalse(client.scroll_kwargs['with_vectors'])

    def test_style_filter_scans_metadata_without_requiring_payload_index(self):
        client = CatalogFilterClient()
        with patch.object(backend_app, '_get_qdrant_client', return_value=client):
            records = backend_app.get_records(limit=12, type='anime')
        self.assertEqual([0, 2], [record['id'] for record in records])
        self.assertEqual(['title', 'name', 'type', 'resolution'], client.scroll_calls[0]['with_payload'])
        self.assertNotIn('scroll_filter', client.scroll_calls[0])
        self.assertEqual([0, 2], client.retrieve_calls[0]['ids'])

    def test_search_scans_metadata_and_normalizes_accents(self):
        client = CatalogFilterClient()
        with patch.object(backend_app, '_get_qdrant_client', return_value=client):
            records = backend_app.get_records(limit=12, search='cafe')
        self.assertEqual([0], [record['id'] for record in records])
        self.assertEqual([0], client.retrieve_calls[0]['ids'])

    def test_filter_without_matches_does_not_request_full_payloads(self):
        client = CatalogFilterClient()
        with patch.object(backend_app, '_get_qdrant_client', return_value=client):
            self.assertEqual([], backend_app.get_records(limit=12, type='sketch'))
        self.assertEqual([], client.retrieve_calls)

    def test_similarity_style_filter_keeps_score_order_and_hydrates_matches(self):
        client = StyleSimilarityClient()
        with patch.object(backend_app, '_get_qdrant_client', return_value=client):
            records = backend_app.get_similar('0', limit=12, type='anime')
        self.assertEqual([2, 4], [record['id'] for record in records])
        self.assertEqual([0.98, 0.96], [record['score'] for record in records])
        self.assertEqual(['anime'], sorted({record['type'] for record in records}))
        self.assertEqual(['title', 'name', 'type', 'resolution'], client.query_kwargs['with_payload'])
        self.assertEqual(13, client.query_kwargs['limit'])
        self.assertEqual([2, 4], client.retrieve_calls[0]['ids'])

    def test_similarity_style_filter_returns_empty_only_after_successful_query(self):
        client = StyleSimilarityClient()
        with patch.object(backend_app, '_get_qdrant_client', return_value=client):
            self.assertEqual([], backend_app.get_similar('0', limit=12, type='sketch'))


if __name__ == '__main__':
    unittest.main()
