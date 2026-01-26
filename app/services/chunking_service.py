"""Chunking service for structure-aware mathematical content splitting.

Implements intelligent chunking that respects LaTeX structure, keeps
theorem-proof blocks together, and maintains mathematical context integrity.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.models.document_line import DocumentLine


class BlockType(str, Enum):
    """Types of content blocks in mathematical documents."""

    THEOREM = "theorem"
    PROOF = "proof"
    DEFINITION = "definition"
    LEMMA = "lemma"
    COROLLARY = "corollary"
    EXAMPLE = "example"
    REMARK = "remark"
    SECTION_HEADER = "section_header"
    NARRATIVE = "narrative"
    THEOREM_PROOF = "theorem_proof"  # Grouped theorem + proof


@dataclass
class Block:
    """Represents a semantic block of content."""

    block_type: BlockType
    text: str
    start_line_id: int
    end_line_id: int
    start_page: int
    end_page: int
    section_path: str = ""
    latex_environments: List[str] = field(default_factory=list)


class ChunkingService:
    """Service for structure-aware chunking of mathematical documents.

    Chunks documents while preserving mathematical context integrity:
    - Never splits mid-equation or mid-proof
    - Keeps theorem+proof as atomic units
    - Respects section boundaries
    - Maintains definition context
    """

    # Target chunk size in tokens
    TARGET_TOKENS = 800
    MIN_TOKENS = 500
    MAX_TOKENS = 2000
    CONTEXT_HEADER_MAX_TOKENS = 500

    # LaTeX environment patterns
    BEGIN_ENV_PATTERN = re.compile(
        r"\\begin\{(theorem|proof|definition|lemma|corollary|example|remark)\}",
        re.IGNORECASE,
    )
    END_ENV_PATTERN = re.compile(
        r"\\end\{(theorem|proof|definition|lemma|corollary|example|remark)\}",
        re.IGNORECASE,
    )

    # Section patterns
    SECTION_PATTERN = re.compile(
        r"\\(section|subsection|subsubsection)\{([^}]+)\}", re.IGNORECASE
    )

    # Russian keyword patterns (for documents without LaTeX environments)
    RUSSIAN_KEYWORDS = {
        BlockType.THEOREM: re.compile(
            r"\\textbf\{Теорема|^Теорема\s+\d+", re.IGNORECASE
        ),
        BlockType.PROOF: re.compile(
            r"\\textbf\{Доказательство\}|^Доказательство[\.:]\s*",
            re.IGNORECASE,
        ),
        BlockType.DEFINITION: re.compile(
            r"\\textbf\{Определение\}|^Определение\s+\d+", re.IGNORECASE
        ),
        BlockType.LEMMA: re.compile(r"\\textbf\{Лемма\}|^Лемма\s+\d+", re.IGNORECASE),
        BlockType.COROLLARY: re.compile(
            r"\\textbf\{Следствие\}|^Следствие\s+\d+", re.IGNORECASE
        ),
        BlockType.EXAMPLE: re.compile(
            r"\\textbf\{Пример\}|^Пример\s+\d+", re.IGNORECASE
        ),
        BlockType.REMARK: re.compile(
            r"\\textbf\{Замечание\}|^Замечание\s+\d+", re.IGNORECASE
        ),
    }

    def chunk_document_lines(self, lines: List[DocumentLine]) -> List[Dict[str, Any]]:
        """Chunk document lines into semantically coherent chunks.

        Args:
            lines: List of DocumentLine objects from Mathpix OCR.

        Returns:
            List of chunk dictionaries with keys: text, chunk_type, start_page,
            end_page, start_line_id, end_line_id, section_path, token_count.
        """
        if not lines:
            return []

        # Step 1: Parse lines into semantic blocks
        blocks = self._parse_blocks(lines)

        # Step 2: Group related blocks (theorem+proof, definition+example)
        blocks = self._group_blocks(blocks)

        # Step 3: Merge small blocks to meet size targets
        blocks = self._merge_small_blocks(blocks)

        # Step 4: Add context headers (prepend definitions)
        blocks = self._add_context_headers(blocks)

        # Step 5: Create final chunk dictionaries with metadata
        chunks = self._create_chunks(blocks)

        return chunks

    def _parse_blocks(self, lines: List[DocumentLine]) -> List[Block]:
        """Parse lines into semantic blocks.

        Identifies LaTeX environments, section headers, and narrative text.

        Args:
            lines: List of DocumentLine objects.

        Returns:
            List of Block objects.
        """
        blocks: List[Block] = []
        current_env: Optional[str] = None
        current_block_lines: List[DocumentLine] = []
        current_block_type: Optional[BlockType] = None

        for line in lines:
            text = line.text.strip()

            # Check for section headers
            section_match = self.SECTION_PATTERN.search(text)
            if section_match:
                # Flush current block
                if current_block_lines:
                    blocks.append(
                        self._create_block(
                            current_block_type or BlockType.NARRATIVE,
                            current_block_lines,
                        )
                    )
                    current_block_lines = []
                    current_block_type = None

                # Add section header block
                blocks.append(self._create_block(BlockType.SECTION_HEADER, [line]))
                continue

            # Check for environment begin
            begin_match = self.BEGIN_ENV_PATTERN.search(text)
            if begin_match:
                # Flush current block
                if current_block_lines:
                    blocks.append(
                        self._create_block(
                            current_block_type or BlockType.NARRATIVE,
                            current_block_lines,
                        )
                    )
                    current_block_lines = []

                # Start new environment
                current_env = begin_match.group(1).lower()
                current_block_type = BlockType(current_env)
                current_block_lines = [line]
                continue

            # Check for environment end
            end_match = self.END_ENV_PATTERN.search(text)
            if end_match and current_env:
                current_block_lines.append(line)
                blocks.append(
                    self._create_block(current_block_type, current_block_lines)
                )
                current_block_lines = []
                current_block_type = None
                current_env = None
                continue

            # Check for Russian keywords (for documents without LaTeX envs)
            if not current_env:
                detected_type = self._detect_russian_keyword(text)
                if detected_type:
                    # Flush current block
                    if current_block_lines:
                        blocks.append(
                            self._create_block(
                                current_block_type or BlockType.NARRATIVE,
                                current_block_lines,
                            )
                        )
                        current_block_lines = []

                    # Start new block with detected type
                    current_block_type = detected_type
                    current_block_lines = [line]
                    continue

            # Regular line within current block or narrative
            if current_env or current_block_type:
                current_block_lines.append(line)
            else:
                # Accumulate narrative text
                current_block_lines.append(line)
                if not current_block_type:
                    current_block_type = BlockType.NARRATIVE

        # Flush remaining block
        if current_block_lines:
            blocks.append(
                self._create_block(
                    current_block_type or BlockType.NARRATIVE, current_block_lines
                )
            )

        return blocks

    def _detect_russian_keyword(self, text: str) -> Optional[BlockType]:
        """Detect Russian mathematical keywords in text.

        Args:
            text: Line text to check.

        Returns:
            BlockType if keyword detected, None otherwise.
        """
        for block_type, pattern in self.RUSSIAN_KEYWORDS.items():
            if pattern.search(text):
                return block_type
        return None

    def _create_block(self, block_type: BlockType, lines: List[DocumentLine]) -> Block:
        """Create Block from list of lines.

        Args:
            block_type: Type of block.
            lines: Lines comprising the block.

        Returns:
            Block object.
        """
        text = "\n".join(line.text for line in lines)
        return Block(
            block_type=block_type,
            text=text,
            start_line_id=lines[0].id,
            end_line_id=lines[-1].id,
            start_page=lines[0].page_number,
            end_page=lines[-1].page_number,
        )

    def _group_blocks(self, blocks: List[Block]) -> List[Block]:
        """Group related blocks (theorem+proof, definition+example).

        Args:
            blocks: List of blocks to group.

        Returns:
            List of blocks with some merged.
        """
        if not blocks:
            return []

        grouped: List[Block] = []
        i = 0

        while i < len(blocks):
            current = blocks[i]

            # Check if next block should be grouped with current
            if i + 1 < len(blocks):
                next_block = blocks[i + 1]

                # Group theorem/lemma/corollary with proof
                if (
                    current.block_type
                    in (
                        BlockType.THEOREM,
                        BlockType.LEMMA,
                        BlockType.COROLLARY,
                    )
                    and next_block.block_type == BlockType.PROOF
                ):
                    grouped_block = Block(
                        block_type=BlockType.THEOREM_PROOF,
                        text=f"{current.text}\n\n{next_block.text}",
                        start_line_id=current.start_line_id,
                        end_line_id=next_block.end_line_id,
                        start_page=current.start_page,
                        end_page=next_block.end_page,
                    )
                    grouped.append(grouped_block)
                    i += 2
                    continue

                # Group definition with immediately following example
                if (
                    current.block_type == BlockType.DEFINITION
                    and next_block.block_type == BlockType.EXAMPLE
                ):
                    grouped_block = Block(
                        block_type=BlockType.DEFINITION,
                        text=f"{current.text}\n\n{next_block.text}",
                        start_line_id=current.start_line_id,
                        end_line_id=next_block.end_line_id,
                        start_page=current.start_page,
                        end_page=next_block.end_page,
                    )
                    grouped.append(grouped_block)
                    i += 2
                    continue

            # No grouping, keep block as-is
            grouped.append(current)
            i += 1

        return grouped

    def _merge_small_blocks(self, blocks: List[Block]) -> List[Block]:
        """Merge small consecutive blocks to reach target size.

        Respects section boundaries and size limits.

        Args:
            blocks: List of blocks to merge.

        Returns:
            List of merged blocks.
        """
        if not blocks:
            return []

        merged: List[Block] = []
        current_merge: List[Block] = []
        current_tokens = 0

        for block in blocks:
            block_tokens = self._count_tokens(block.text)

            # Section headers are strong boundaries - flush and don't merge
            if block.block_type == BlockType.SECTION_HEADER:
                if current_merge:
                    merged.append(self._merge_block_list(current_merge))
                    current_merge = []
                    current_tokens = 0
                merged.append(block)
                continue

            # Check if adding this block would exceed max size
            if current_tokens + block_tokens > self.MAX_TOKENS and current_merge:
                # Flush current merge
                merged.append(self._merge_block_list(current_merge))
                current_merge = [block]
                current_tokens = block_tokens
            else:
                # Add to current merge
                current_merge.append(block)
                current_tokens += block_tokens

                # If we've reached target size, flush
                if current_tokens >= self.TARGET_TOKENS:
                    merged.append(self._merge_block_list(current_merge))
                    current_merge = []
                    current_tokens = 0

        # Flush remaining merge
        if current_merge:
            merged.append(self._merge_block_list(current_merge))

        return merged

    def _merge_block_list(self, blocks: List[Block]) -> Block:
        """Merge list of blocks into single block.

        Args:
            blocks: Blocks to merge.

        Returns:
            Single merged block.
        """
        if len(blocks) == 1:
            return blocks[0]

        # Use first non-narrative type if available
        block_type = blocks[0].block_type
        for b in blocks:
            if b.block_type != BlockType.NARRATIVE:
                block_type = b.block_type
                break

        return Block(
            block_type=block_type,
            text="\n\n".join(b.text for b in blocks),
            start_line_id=blocks[0].start_line_id,
            end_line_id=blocks[-1].end_line_id,
            start_page=blocks[0].start_page,
            end_page=blocks[-1].end_page,
        )

    def _add_context_headers(self, blocks: List[Block]) -> List[Block]:
        """Add definition context to theorem/proof blocks.

        Prepends relevant definitions to provide context.

        Args:
            blocks: List of blocks.

        Returns:
            List of blocks with context headers added.
        """
        # Track recent definitions (last 3)
        recent_definitions: List[Block] = []

        result: List[Block] = []

        for block in blocks:
            # Track definitions
            if block.block_type == BlockType.DEFINITION:
                recent_definitions.append(block)
                # Keep only last 3 definitions
                if len(recent_definitions) > 3:
                    recent_definitions.pop(0)

            # Add context to theorems/proofs
            if block.block_type in (
                BlockType.THEOREM,
                BlockType.THEOREM_PROOF,
                BlockType.LEMMA,
                BlockType.COROLLARY,
            ):
                if recent_definitions:
                    # Create context header from recent definitions
                    context_parts = []
                    context_tokens = 0

                    for defn in reversed(recent_definitions):
                        defn_tokens = self._count_tokens(defn.text)
                        if (
                            context_tokens + defn_tokens
                            <= self.CONTEXT_HEADER_MAX_TOKENS
                        ):
                            context_parts.insert(0, defn.text)
                            context_tokens += defn_tokens
                        else:
                            break

                    if context_parts:
                        context_header = (
                            "Context:\n" + "\n\n".join(context_parts) + "\n\n---\n\n"
                        )
                        block = Block(
                            block_type=block.block_type,
                            text=context_header + block.text,
                            start_line_id=block.start_line_id,
                            end_line_id=block.end_line_id,
                            start_page=block.start_page,
                            end_page=block.end_page,
                        )

            result.append(block)

        return result

    def _create_chunks(self, blocks: List[Block]) -> List[Dict[str, Any]]:
        """Create final chunk dictionaries with metadata.

        Args:
            blocks: List of blocks to convert to chunks.

        Returns:
            List of chunk dictionaries.
        """
        chunks: List[Dict[str, Any]] = []
        current_section_path = ""

        for block in blocks:
            # Update section path when we hit section headers
            if block.block_type == BlockType.SECTION_HEADER:
                section_match = self.SECTION_PATTERN.search(block.text)
                if section_match:
                    section_level = section_match.group(1)
                    section_title = section_match.group(2)

                    if section_level == "section":
                        current_section_path = section_title
                    elif section_level == "subsection":
                        # Add to existing path
                        if current_section_path:
                            current_section_path += f" > {section_title}"
                        else:
                            current_section_path = section_title
                    elif section_level == "subsubsection":
                        if current_section_path:
                            current_section_path += f" > {section_title}"
                        else:
                            current_section_path = section_title

            chunk = {
                "text": block.text,
                "chunk_type": block.block_type.value,
                "start_page": block.start_page,
                "end_page": block.end_page,
                "start_line_id": block.start_line_id,
                "end_line_id": block.end_line_id,
                "section_path": current_section_path,
                "token_count": self._count_tokens(block.text),
            }
            chunks.append(chunk)

        return chunks

    def _count_tokens(self, text: str) -> int:
        """Count approximate tokens in text.

        Uses simple word-based counting as approximation.
        Math notation and Russian text are handled.

        Args:
            text: Text to count tokens for.

        Returns:
            Approximate token count.
        """
        if not text:
            return 0

        # Simple word-based tokenization
        # Split on whitespace and count
        words = text.split()

        # Adjust for LaTeX commands and math notation
        # Rough heuristic: LaTeX commands ~1.5x multiplier
        latex_commands = len(re.findall(r"\\[a-zA-Z]+", text))

        return len(words) + int(latex_commands * 0.5)
