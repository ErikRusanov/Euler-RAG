"""Chunking service for structure-aware mathematical content splitting.

Implements intelligent chunking that respects LaTeX structure, keeps
theorem-proof blocks together, and maintains mathematical context integrity.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import tiktoken

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
    PROPOSITION = "proposition"
    TASK = "task"
    ASSERTION = "assertion"
    NOTE = "note"
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

    # Section level hierarchy
    SECTION_LEVELS = {"section": 1, "subsection": 2, "subsubsection": 3}

    # LaTeX environment patterns (structural blocks only)
    STRUCTURAL_ENVS = {
        "theorem",
        "proof",
        "definition",
        "lemma",
        "corollary",
        "example",
        "remark",
        "proposition",
        "assertion",
        "task",
        "note",
    }
    BEGIN_ENV_PATTERN = re.compile(
        r"\\begin\{(theorem|proof|definition|lemma|corollary|example|remark|"
        r"proposition|assertion|task|note)\}",
        re.IGNORECASE,
    )
    END_ENV_PATTERN = re.compile(
        r"\\end\{(theorem|proof|definition|lemma|corollary|example|remark|"
        r"proposition|assertion|task|note)\}",
        re.IGNORECASE,
    )

    # Section patterns - LaTeX style
    SECTION_PATTERN = re.compile(
        r"\\(section|subsection|subsubsection)\{([^}]+)\}", re.IGNORECASE
    )

    # Markdown header patterns (Mathpix often outputs these)
    MARKDOWN_HEADER_PATTERN = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)

    # Russian keyword patterns (for documents without LaTeX environments)
    RUSSIAN_KEYWORDS = {
        BlockType.THEOREM: re.compile(
            r"\\textbf\{Теорема\}|\b(?:Теорема|Теор\.|Т-ма)\b\.?\s*\d*", re.IGNORECASE
        ),
        BlockType.PROOF: re.compile(
            r"\\textbf\{Доказательство\}|"
            r"\b(?:Доказательство|Док-во|Доказ\.|Д-во)\b\.?[:\s]*",
            re.IGNORECASE,
        ),
        BlockType.DEFINITION: re.compile(
            r"\\textbf\{Определение\}|\b(?:Определение|Опр\.|Опр-ие)\b\.?\s*\d*",
            re.IGNORECASE,
        ),
        BlockType.LEMMA: re.compile(
            r"\\textbf\{Лемма\}|\b(?:Лемма|Лем\.)\b\.?\s*\d*", re.IGNORECASE
        ),
        BlockType.COROLLARY: re.compile(
            r"\\textbf\{Следствие\}|\b(?:Следствие|След\.|Сл-ие)\b\.?\s*\d*",
            re.IGNORECASE,
        ),
        BlockType.EXAMPLE: re.compile(
            r"\\textbf\{Пример\}|\bПример\b\.?\s*\d*", re.IGNORECASE
        ),
        BlockType.REMARK: re.compile(
            r"\\textbf\{(?:Замечание|Примечание)\}|"
            r"\b(?:Замечание|Зам\.|Примечание|Прим\.)\b\.?\s*\d*",
            re.IGNORECASE,
        ),
        BlockType.PROPOSITION: re.compile(
            r"\\textbf\{(?:Утверждение|Предложение)\}|"
            r"\b(?:Утверждение|Утв\.|Предложение|Предл\.)\b\.?\s*\d*",
            re.IGNORECASE,
        ),
        BlockType.TASK: re.compile(
            r"\\textbf\{Задача\}|\b(?:Задача|Зад\.)\b\.?\s*\d*", re.IGNORECASE
        ),
    }

    def __init__(self) -> None:
        """Initialize ChunkingService with tiktoken encoder."""
        # Use cl100k_base encoding (GPT-4 compatible)
        self._encoder = tiktoken.get_encoding("cl100k_base")

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
        Uses stack-based approach to handle nested environments correctly.

        Args:
            lines: List of DocumentLine objects.

        Returns:
            List of Block objects.
        """
        blocks: List[Block] = []
        env_stack: List[str] = []  # Stack for tracking nested environments
        current_block_lines: List[DocumentLine] = []
        current_block_type: Optional[BlockType] = None

        for line in lines:
            text = line.text.strip()

            # Check for section headers (LaTeX or Markdown)
            section_info = self._detect_section_header(text)
            if section_info:
                # Section headers only flush blocks if we're not inside a proof/theorem
                if not env_stack:
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
                else:
                    # Inside an environment, treat as content
                    current_block_lines.append(line)
                    continue

            # Check for environment begin
            begin_match = self.BEGIN_ENV_PATTERN.search(text)
            if begin_match:
                env_name = begin_match.group(1).lower()

                # If not in any environment, start a new block
                if not env_stack:
                    # Flush current narrative block
                    if current_block_lines:
                        blocks.append(
                            self._create_block(
                                current_block_type or BlockType.NARRATIVE,
                                current_block_lines,
                            )
                        )
                        current_block_lines = []

                    # Start new environment block
                    current_block_type = BlockType(env_name)
                    current_block_lines = [line]
                    env_stack.append(env_name)
                else:
                    # Already inside an environment - this is nested
                    # Just add line to current block, don't start new block
                    current_block_lines.append(line)
                    env_stack.append(env_name)
                continue

            # Check for environment end
            end_match = self.END_ENV_PATTERN.search(text)
            if end_match and env_stack:
                end_env_name = end_match.group(1).lower()
                current_block_lines.append(line)

                # Pop from stack (handle mismatched ends gracefully)
                if env_stack and env_stack[-1] == end_env_name:
                    env_stack.pop()

                # If stack is empty, we've closed the outermost environment
                if not env_stack:
                    blocks.append(
                        self._create_block(current_block_type, current_block_lines)
                    )
                    current_block_lines = []
                    current_block_type = None
                continue

            # Check for Russian keywords (only if not inside an environment)
            if not env_stack:
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
            current_block_lines.append(line)
            if not current_block_type and not env_stack:
                current_block_type = BlockType.NARRATIVE

        # Flush remaining block
        if current_block_lines:
            blocks.append(
                self._create_block(
                    current_block_type or BlockType.NARRATIVE, current_block_lines
                )
            )

        return blocks

    def _detect_section_header(self, text: str) -> Optional[Dict[str, Any]]:
        """Detect section header in LaTeX or Markdown format.

        Args:
            text: Line text to check.

        Returns:
            Dict with 'level' and 'title' if detected, None otherwise.
        """
        # Check LaTeX style
        latex_match = self.SECTION_PATTERN.search(text)
        if latex_match:
            level_name = latex_match.group(1).lower()
            return {
                "level": self.SECTION_LEVELS.get(level_name, 1),
                "title": latex_match.group(2),
                "style": "latex",
            }

        # Check Markdown style (## Header)
        md_match = self.MARKDOWN_HEADER_PATTERN.match(text)
        if md_match:
            hashes = md_match.group(1)
            return {
                "level": len(hashes),
                "title": md_match.group(2).strip(),
                "style": "markdown",
            }

        return None

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

        Allows small narrative gaps between theorem and proof for more
        realistic grouping.

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

            # Check if current is a theorem/lemma/corollary/proposition that might be
            # followed by a proof (possibly with small gap)
            if current.block_type in (
                BlockType.THEOREM,
                BlockType.LEMMA,
                BlockType.COROLLARY,
                BlockType.PROPOSITION,
            ):
                # Look for proof within next 2 blocks (allowing 1 narrative gap)
                proof_idx = None
                gap_blocks: List[Block] = []

                for j in range(i + 1, min(i + 3, len(blocks))):
                    candidate = blocks[j]

                    # Stop if we hit a section header
                    if candidate.block_type == BlockType.SECTION_HEADER:
                        break

                    if candidate.block_type == BlockType.PROOF:
                        proof_idx = j
                        break
                    elif candidate.block_type == BlockType.NARRATIVE:
                        # Allow one small narrative gap (e.g., "Рассмотрим...")
                        if self._count_tokens(candidate.text) < 100:
                            gap_blocks.append(candidate)
                        else:
                            break
                    else:
                        # Hit another structural block, stop looking
                        break

                if proof_idx is not None:
                    # Group theorem + gap + proof
                    combined_text = current.text
                    for gap in gap_blocks:
                        combined_text += "\n\n" + gap.text
                    combined_text += "\n\n" + blocks[proof_idx].text

                    grouped_block = Block(
                        block_type=BlockType.THEOREM_PROOF,
                        text=combined_text,
                        start_line_id=current.start_line_id,
                        end_line_id=blocks[proof_idx].end_line_id,
                        start_page=current.start_page,
                        end_page=blocks[proof_idx].end_page,
                    )
                    grouped.append(grouped_block)
                    i = proof_idx + 1
                    continue

            # Check for definition followed by example
            if current.block_type == BlockType.DEFINITION and i + 1 < len(blocks):
                next_block = blocks[i + 1]
                if next_block.block_type == BlockType.EXAMPLE:
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
        Clears definitions on section boundaries to prevent context bleeding.

        Args:
            blocks: List of blocks.

        Returns:
            List of blocks with context headers added.
        """
        # Track recent definitions (last 3) - cleared on section change
        recent_definitions: List[Block] = []

        result: List[Block] = []

        for block in blocks:
            # Clear definitions on section boundary (prevent context bleeding)
            if block.block_type == BlockType.SECTION_HEADER:
                recent_definitions = []

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
                BlockType.PROPOSITION,
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

        Uses stack-based section tracking for correct hierarchy.

        Args:
            blocks: List of blocks to convert to chunks.

        Returns:
            List of chunk dictionaries.
        """
        chunks: List[Dict[str, Any]] = []
        # Stack-based section tracking: {level: title}
        section_stack: Dict[int, str] = {}

        for block in blocks:
            # Update section path when we hit section headers
            if block.block_type == BlockType.SECTION_HEADER:
                section_info = self._detect_section_header(block.text)
                if section_info:
                    current_level = section_info["level"]
                    section_title = section_info["title"]

                    # Clear all levels >= current (handle sibling sections)
                    keys_to_remove = [k for k in section_stack if k >= current_level]
                    for k in keys_to_remove:
                        del section_stack[k]

                    # Add current section to stack
                    section_stack[current_level] = section_title

            # Build section path from stack
            sorted_titles = [section_stack[k] for k in sorted(section_stack.keys())]
            current_section_path = " > ".join(sorted_titles)

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
        """Count tokens in text using tiktoken.

        Uses cl100k_base encoding for GPT-4 compatible token counting.

        Args:
            text: Text to count tokens for.

        Returns:
            Token count.
        """
        if not text:
            return 0

        return len(self._encoder.encode(text))
