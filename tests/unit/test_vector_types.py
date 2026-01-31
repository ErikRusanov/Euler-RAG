"""Unit tests for vector type support."""

from app.utils.vector_types import Vector


class TestVectorType:
    """Test suite for pgvector Vector type."""

    def test_get_col_spec(self):
        """Test column specification generation."""
        vector_type = Vector(1024)
        assert vector_type.get_col_spec() == "vector(1024)"

        vector_type_512 = Vector(512)
        assert vector_type_512.get_col_spec() == "vector(512)"

    def test_bind_processor_with_valid_list(self):
        """Test vector serialization from list to string."""
        vector_type = Vector(3)
        processor = vector_type.bind_processor(dialect=None)

        # Test normal vector
        result = processor([0.1, 0.2, 0.3])
        assert result == "[0.1,0.2,0.3]"

        # Test negative values
        result = processor([-1.5, 0.0, 2.7])
        assert result == "[-1.5,0.0,2.7]"

    def test_bind_processor_with_none(self):
        """Test vector serialization with None value."""
        vector_type = Vector(1024)
        processor = vector_type.bind_processor(dialect=None)

        result = processor(None)
        assert result is None

    def test_result_processor_with_valid_string(self):
        """Test vector deserialization from string to list."""
        vector_type = Vector(3)
        processor = vector_type.result_processor(dialect=None, coltype=None)

        # Test normal vector
        result = processor("[0.1,0.2,0.3]")
        assert result == [0.1, 0.2, 0.3]

        # Test negative values
        result = processor("[-1.5,0.0,2.7]")
        assert result == [-1.5, 0.0, 2.7]

    def test_result_processor_with_none(self):
        """Test vector deserialization with None value."""
        vector_type = Vector(1024)
        processor = vector_type.result_processor(dialect=None, coltype=None)

        result = processor(None)
        assert result is None

    def test_cache_ok_flag(self):
        """Test that cache_ok is set to True for SQLAlchemy caching."""
        vector_type = Vector(1024)
        assert vector_type.cache_ok is True

    def test_round_trip_serialization(self):
        """Test full round-trip: list -> string -> list."""
        vector_type = Vector(5)

        # Bind processor (Python -> DB)
        bind_proc = vector_type.bind_processor(dialect=None)
        # Result processor (DB -> Python)
        result_proc = vector_type.result_processor(dialect=None, coltype=None)

        original = [0.1, 0.2, 0.3, 0.4, 0.5]
        serialized = bind_proc(original)
        deserialized = result_proc(serialized)

        assert deserialized == original
        assert isinstance(deserialized, list)
        assert all(isinstance(v, float) for v in deserialized)

    def test_large_dimension_vector(self):
        """Test with realistic embedding dimension (1024)."""
        vector_type = Vector(1024)
        bind_proc = vector_type.bind_processor(dialect=None)
        result_proc = vector_type.result_processor(dialect=None, coltype=None)

        # Create 1024-dimensional vector
        original = [0.1] * 1024
        serialized = bind_proc(original)
        deserialized = result_proc(serialized)

        assert len(deserialized) == 1024
        assert deserialized == original
