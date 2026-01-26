"""Unit tests for ChunkingService."""

from unittest.mock import Mock

import pytest

from app.models.document_line import DocumentLine
from app.services.chunking_service import Block, BlockType, ChunkingService


class TestBlockDetection:
    """Tests for LaTeX block detection."""

    @pytest.fixture
    def chunking_service(self):
        """Create ChunkingService instance."""
        return ChunkingService()

    def _create_line(
        self, page: int, line_num: int, text: str, line_type: str = "text"
    ) -> DocumentLine:
        """Helper to create mock DocumentLine."""
        line = Mock(spec=DocumentLine)
        line.id = line_num
        line.page_number = page
        line.line_number = line_num
        line.text = text
        line.line_type = line_type
        return line

    def test_detects_theorem_block(self, chunking_service: ChunkingService):
        """Service detects \\begin{theorem} blocks."""
        lines = [
            self._create_line(1, 1, "\\begin{theorem}"),
            self._create_line(1, 2, "If $f$ is continuous, then..."),
            self._create_line(1, 3, "\\end{theorem}"),
        ]

        blocks = chunking_service._parse_blocks(lines)

        assert len(blocks) == 1
        assert blocks[0].block_type == BlockType.THEOREM
        assert "continuous" in blocks[0].text

    def test_detects_proof_block(self, chunking_service: ChunkingService):
        """Service detects \\begin{proof} blocks."""
        lines = [
            self._create_line(1, 1, "\\begin{proof}"),
            self._create_line(1, 2, "By contradiction, assume..."),
            self._create_line(1, 3, "\\end{proof}"),
        ]

        blocks = chunking_service._parse_blocks(lines)

        assert len(blocks) == 1
        assert blocks[0].block_type == BlockType.PROOF
        assert "contradiction" in blocks[0].text

    def test_detects_definition_block(self, chunking_service: ChunkingService):
        """Service detects \\begin{definition} blocks."""
        lines = [
            self._create_line(1, 1, "\\begin{definition}"),
            self._create_line(1, 2, "A function $f$ is called continuous if..."),
            self._create_line(1, 3, "\\end{definition}"),
        ]

        blocks = chunking_service._parse_blocks(lines)

        assert len(blocks) == 1
        assert blocks[0].block_type == BlockType.DEFINITION
        assert "continuous" in blocks[0].text

    def test_detects_example_block(self, chunking_service: ChunkingService):
        """Service detects \\begin{example} blocks."""
        lines = [
            self._create_line(1, 1, "\\begin{example}"),
            self._create_line(1, 2, "Consider the function $f(x) = x^2$..."),
            self._create_line(1, 3, "\\end{example}"),
        ]

        blocks = chunking_service._parse_blocks(lines)

        assert len(blocks) == 1
        assert blocks[0].block_type == BlockType.EXAMPLE

    def test_detects_lemma_block(self, chunking_service: ChunkingService):
        """Service detects \\begin{lemma} blocks."""
        lines = [
            self._create_line(1, 1, "\\begin{lemma}"),
            self._create_line(1, 2, "For all $x > 0$..."),
            self._create_line(1, 3, "\\end{lemma}"),
        ]

        blocks = chunking_service._parse_blocks(lines)

        assert len(blocks) == 1
        assert blocks[0].block_type == BlockType.LEMMA

    def test_detects_corollary_block(self, chunking_service: ChunkingService):
        """Service detects \\begin{corollary} blocks."""
        lines = [
            self._create_line(1, 1, "\\begin{corollary}"),
            self._create_line(1, 2, "It follows that..."),
            self._create_line(1, 3, "\\end{corollary}"),
        ]

        blocks = chunking_service._parse_blocks(lines)

        assert len(blocks) == 1
        assert blocks[0].block_type == BlockType.COROLLARY

    def test_detects_section_header(self, chunking_service: ChunkingService):
        """Service detects \\section{} headers."""
        lines = [
            self._create_line(1, 1, "\\section{Calculus of Variations}"),
        ]

        blocks = chunking_service._parse_blocks(lines)

        assert len(blocks) == 1
        assert blocks[0].block_type == BlockType.SECTION_HEADER
        assert "Calculus of Variations" in blocks[0].text

    def test_detects_subsection_header(self, chunking_service: ChunkingService):
        """Service detects \\subsection{} headers."""
        lines = [
            self._create_line(1, 1, "\\subsection{Euler-Lagrange Equation}"),
        ]

        blocks = chunking_service._parse_blocks(lines)

        assert len(blocks) == 1
        assert blocks[0].block_type == BlockType.SECTION_HEADER

    def test_narrative_text_as_narrative_block(self, chunking_service: ChunkingService):
        """Service treats plain text as narrative blocks."""
        lines = [
            self._create_line(1, 1, "In this chapter, we will explore..."),
            self._create_line(1, 2, "The fundamental concepts are..."),
        ]

        blocks = chunking_service._parse_blocks(lines)

        assert len(blocks) == 1
        assert blocks[0].block_type == BlockType.NARRATIVE

    def test_handles_russian_theorem_keywords(self, chunking_service: ChunkingService):
        """Service detects Russian theorem keywords (Теорема, Доказательство)."""
        lines = [
            self._create_line(1, 1, "\\textbf{Теорема 1.}"),
            self._create_line(1, 2, "Пусть $f$ - непрерывная функция..."),
        ]

        blocks = chunking_service._parse_blocks(lines)

        assert len(blocks) > 0
        # Should detect as theorem even without \begin{theorem}
        assert any(b.block_type == BlockType.THEOREM for b in blocks)

    def test_preserves_line_references(self, chunking_service: ChunkingService):
        """Service preserves start and end line IDs."""
        lines = [
            self._create_line(1, 1, "\\begin{theorem}"),
            self._create_line(1, 2, "Content"),
            self._create_line(1, 3, "\\end{theorem}"),
        ]

        blocks = chunking_service._parse_blocks(lines)

        assert blocks[0].start_line_id == 1
        assert blocks[0].end_line_id == 3
        assert blocks[0].start_page == 1
        assert blocks[0].end_page == 1


class TestBlockGrouping:
    """Tests for grouping related blocks together."""

    @pytest.fixture
    def chunking_service(self):
        """Create ChunkingService instance."""
        return ChunkingService()

    def test_groups_theorem_with_proof(self, chunking_service: ChunkingService):
        """Service groups theorem immediately followed by proof."""
        blocks = [
            Block(
                block_type=BlockType.THEOREM,
                text="Theorem: If f is continuous...",
                start_line_id=1,
                end_line_id=2,
                start_page=1,
                end_page=1,
            ),
            Block(
                block_type=BlockType.PROOF,
                text="Proof: By contradiction...",
                start_line_id=3,
                end_line_id=5,
                start_page=1,
                end_page=1,
            ),
        ]

        grouped = chunking_service._group_blocks(blocks)

        assert len(grouped) == 1
        assert grouped[0].block_type == BlockType.THEOREM_PROOF
        assert "Theorem" in grouped[0].text
        assert "Proof" in grouped[0].text

    def test_groups_definition_with_example(self, chunking_service: ChunkingService):
        """Service groups definition immediately followed by example."""
        blocks = [
            Block(
                block_type=BlockType.DEFINITION,
                text="Definition: A metric space is...",
                start_line_id=1,
                end_line_id=2,
                start_page=1,
                end_page=1,
            ),
            Block(
                block_type=BlockType.EXAMPLE,
                text="Example: Consider R^n with Euclidean metric...",
                start_line_id=3,
                end_line_id=5,
                start_page=1,
                end_page=1,
            ),
        ]

        grouped = chunking_service._group_blocks(blocks)

        assert len(grouped) == 1
        assert "Definition" in grouped[0].text
        assert "Example" in grouped[0].text

    def test_groups_lemma_with_proof(self, chunking_service: ChunkingService):
        """Service groups lemma with its proof."""
        blocks = [
            Block(
                block_type=BlockType.LEMMA,
                text="Lemma: For all x > 0...",
                start_line_id=1,
                end_line_id=2,
                start_page=1,
                end_page=1,
            ),
            Block(
                block_type=BlockType.PROOF,
                text="Proof: Direct calculation...",
                start_line_id=3,
                end_line_id=4,
                start_page=1,
                end_page=1,
            ),
        ]

        grouped = chunking_service._group_blocks(blocks)

        assert len(grouped) == 1
        assert "Lemma" in grouped[0].text
        assert "Proof" in grouped[0].text

    def test_does_not_group_separated_blocks(self, chunking_service: ChunkingService):
        """Service does not group blocks separated by other content."""
        blocks = [
            Block(
                block_type=BlockType.THEOREM,
                text="Theorem 1",
                start_line_id=1,
                end_line_id=2,
                start_page=1,
                end_page=1,
            ),
            Block(
                block_type=BlockType.NARRATIVE,
                text="Some discussion...",
                start_line_id=3,
                end_line_id=4,
                start_page=1,
                end_page=1,
            ),
            Block(
                block_type=BlockType.PROOF,
                text="Proof of Theorem 1",
                start_line_id=5,
                end_line_id=6,
                start_page=1,
                end_page=1,
            ),
        ]

        grouped = chunking_service._group_blocks(blocks)

        # Should not group because narrative separates them
        assert len(grouped) == 3


class TestSectionTracking:
    """Tests for maintaining section hierarchy."""

    @pytest.fixture
    def chunking_service(self):
        """Create ChunkingService instance."""
        return ChunkingService()

    def test_tracks_section_hierarchy(self, chunking_service: ChunkingService):
        """Service tracks current section path."""
        blocks = [
            Block(
                block_type=BlockType.SECTION_HEADER,
                text="\\section{Chapter 3: Calculus}",
                start_line_id=1,
                end_line_id=1,
                start_page=1,
                end_page=1,
            ),
            Block(
                block_type=BlockType.THEOREM,
                text="Theorem 3.1",
                start_line_id=2,
                end_line_id=3,
                start_page=1,
                end_page=1,
            ),
        ]

        chunks = chunking_service._create_chunks(blocks)

        assert "section_path" in chunks[0]
        assert "Calculus" in chunks[0]["section_path"]

    def test_tracks_nested_sections(self, chunking_service: ChunkingService):
        """Service tracks nested section/subsection hierarchy."""
        blocks = [
            Block(
                block_type=BlockType.SECTION_HEADER,
                text="\\section{Calculus of Variations}",
                start_line_id=1,
                end_line_id=1,
                start_page=1,
                end_page=1,
            ),
            Block(
                block_type=BlockType.SECTION_HEADER,
                text="\\subsection{Euler-Lagrange Equation}",
                start_line_id=2,
                end_line_id=2,
                start_page=1,
                end_page=1,
            ),
            Block(
                block_type=BlockType.THEOREM,
                text="Theorem",
                start_line_id=3,
                end_line_id=4,
                start_page=1,
                end_page=1,
            ),
        ]

        chunks = chunking_service._create_chunks(blocks)

        # Check the theorem chunk (last one) has full nested path
        assert len(chunks) == 3
        theorem_chunk = chunks[2]
        assert "section_path" in theorem_chunk
        path = theorem_chunk["section_path"]
        assert "Calculus of Variations" in path
        assert "Euler-Lagrange" in path


class TestChunkMerging:
    """Tests for size-aware chunk merging."""

    @pytest.fixture
    def chunking_service(self):
        """Create ChunkingService instance."""
        return ChunkingService()

    def test_merges_small_blocks_under_target(self, chunking_service: ChunkingService):
        """Service merges consecutive small blocks to reach target size."""
        # Create blocks with ~100 tokens each
        blocks = [
            Block(
                block_type=BlockType.NARRATIVE,
                text="Short text " * 50,  # ~100 tokens
                start_line_id=1,
                end_line_id=2,
                start_page=1,
                end_page=1,
            ),
            Block(
                block_type=BlockType.NARRATIVE,
                text="Another short text " * 50,
                start_line_id=3,
                end_line_id=4,
                start_page=1,
                end_page=1,
            ),
        ]

        merged = chunking_service._merge_small_blocks(blocks)

        # Should merge into one chunk since both are well under 500 token minimum
        assert len(merged) < len(blocks)

    def test_does_not_merge_beyond_max_size(self, chunking_service: ChunkingService):
        """Service does not merge blocks if result exceeds max size."""
        # Create blocks that are ~1000 tokens each
        large_text = "word " * 1000
        blocks = [
            Block(
                block_type=BlockType.NARRATIVE,
                text=large_text,
                start_line_id=1,
                end_line_id=2,
                start_page=1,
                end_page=1,
            ),
            Block(
                block_type=BlockType.NARRATIVE,
                text=large_text,
                start_line_id=3,
                end_line_id=4,
                start_page=1,
                end_page=1,
            ),
        ]

        merged = chunking_service._merge_small_blocks(blocks)

        # Should not merge because combined size > 2000 tokens
        assert len(merged) == 2

    def test_respects_section_boundaries(self, chunking_service: ChunkingService):
        """Service does not merge across section boundaries."""
        blocks = [
            Block(
                block_type=BlockType.NARRATIVE,
                text="Content in section 1 " * 50,
                start_line_id=1,
                end_line_id=2,
                start_page=1,
                end_page=1,
            ),
            Block(
                block_type=BlockType.SECTION_HEADER,
                text="\\section{New Section}",
                start_line_id=3,
                end_line_id=3,
                start_page=1,
                end_page=1,
            ),
            Block(
                block_type=BlockType.NARRATIVE,
                text="Content in section 2 " * 50,
                start_line_id=4,
                end_line_id=5,
                start_page=1,
                end_page=1,
            ),
        ]

        merged = chunking_service._merge_small_blocks(blocks)

        # Should not merge across section header
        assert len(merged) >= 2


class TestContextHeaders:
    """Tests for adding definition context to chunks."""

    @pytest.fixture
    def chunking_service(self):
        """Create ChunkingService instance."""
        return ChunkingService()

    def test_adds_definition_context_to_theorem(
        self, chunking_service: ChunkingService
    ):
        """Service prepends relevant definitions to theorem chunks."""
        blocks = [
            Block(
                block_type=BlockType.DEFINITION,
                text="Definition: A metric space (X, d) is...",
                start_line_id=1,
                end_line_id=2,
                start_page=1,
                end_page=1,
            ),
            Block(
                block_type=BlockType.THEOREM_PROOF,
                text="Theorem: Every metric space is Hausdorff. Proof: ...",
                start_line_id=3,
                end_line_id=5,
                start_page=1,
                end_page=1,
            ),
        ]

        chunks = chunking_service._add_context_headers(blocks)

        # Theorem chunk should have definition prepended
        theorem_chunk = next(c for c in chunks if "Theorem" in c.text)
        assert "Definition" in theorem_chunk.text
        assert theorem_chunk.text.index("Definition") < theorem_chunk.text.index(
            "Theorem"
        )

    def test_limits_context_header_size(self, chunking_service: ChunkingService):
        """Service limits context header to prevent bloat."""
        # Create many definitions
        blocks = [
            Block(
                block_type=BlockType.DEFINITION,
                text=f"Definition {i}: " + "text " * 100,
                start_line_id=i,
                end_line_id=i,
                start_page=1,
                end_page=1,
            )
            for i in range(10)
        ]
        blocks.append(
            Block(
                block_type=BlockType.THEOREM,
                text="Theorem: ...",
                start_line_id=11,
                end_line_id=12,
                start_page=1,
                end_page=1,
            )
        )

        chunks = chunking_service._add_context_headers(blocks)

        # Should not prepend all 10 definitions (would be too large)
        theorem_chunk = next(c for c in chunks if "Theorem" in c.text)
        token_count = chunking_service._count_tokens(theorem_chunk.text)
        assert token_count < 2500  # Reasonable limit


class TestTokenCounting:
    """Tests for token counting."""

    @pytest.fixture
    def chunking_service(self):
        """Create ChunkingService instance."""
        return ChunkingService()

    def test_counts_tokens_approximately(self, chunking_service: ChunkingService):
        """Service counts tokens with reasonable accuracy."""
        text = "This is a test sentence with multiple words."
        count = chunking_service._count_tokens(text)

        # Should be roughly 9-10 tokens
        assert 8 <= count <= 12

    def test_handles_latex_math(self, chunking_service: ChunkingService):
        """Service counts LaTeX math notation."""
        text = r"The integral $\int_0^\infty e^{-x} dx = 1$ is fundamental."
        count = chunking_service._count_tokens(text)

        # Math notation should be counted
        assert count >= 10

    def test_handles_russian_text(self, chunking_service: ChunkingService):
        """Service counts Russian characters correctly."""
        text = "Пусть f - непрерывная функция на отрезке [a, b]."
        count = chunking_service._count_tokens(text)

        # Should count Russian words
        assert count > 5


class TestFullChunkingWorkflow:
    """Tests for complete chunking workflow."""

    @pytest.fixture
    def chunking_service(self):
        """Create ChunkingService instance."""
        return ChunkingService()

    def _create_line(
        self, page: int, line_num: int, text: str, line_type: str = "text"
    ) -> DocumentLine:
        """Helper to create mock DocumentLine."""
        line = Mock(spec=DocumentLine)
        line.id = line_num
        line.page_number = page
        line.line_number = line_num
        line.text = text
        line.line_type = line_type
        return line

    def test_chunks_simple_document(self, chunking_service: ChunkingService):
        """Service chunks a simple document with definition and theorem."""
        lines = [
            self._create_line(1, 1, "\\section{Introduction}"),
            self._create_line(1, 2, "\\begin{definition}"),
            self._create_line(1, 3, "A function f is continuous if..."),
            self._create_line(1, 4, "\\end{definition}"),
            self._create_line(1, 5, "\\begin{theorem}"),
            self._create_line(1, 6, "Every continuous function on [a,b] is bounded."),
            self._create_line(1, 7, "\\end{theorem}"),
            self._create_line(1, 8, "\\begin{proof}"),
            self._create_line(1, 9, "By compactness..."),
            self._create_line(1, 10, "\\end{proof}"),
        ]

        chunks = chunking_service.chunk_document_lines(lines)

        assert len(chunks) > 0
        assert all("text" in chunk for chunk in chunks)
        assert all("chunk_type" in chunk for chunk in chunks)
        assert all("start_page" in chunk for chunk in chunks)

    def test_includes_metadata_in_chunks(self, chunking_service: ChunkingService):
        """Service includes required metadata in chunks."""
        lines = [
            self._create_line(1, 1, "\\section{Calculus}"),
            self._create_line(1, 2, "\\begin{theorem}"),
            self._create_line(1, 3, "Content"),
            self._create_line(1, 4, "\\end{theorem}"),
        ]

        chunks = chunking_service.chunk_document_lines(lines)

        assert len(chunks) > 0
        chunk = chunks[0]
        assert "section_path" in chunk
        assert "chunk_type" in chunk
        assert "start_line_id" in chunk
        assert "end_line_id" in chunk
        assert "token_count" in chunk
