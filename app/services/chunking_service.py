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
    LIST_ITEM = "list_item"
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
    TARGET_TOKENS = 500
    MIN_TOKENS = 500
    MAX_TOKENS = 1000
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

    # Book-style section patterns (Russian book formatting)
    # Matches: "§ 1a. Название" or "1. Портфель ценных бумаг"
    # Must start at beginning of line and be followed by capital letter
    BOOK_SECTION_PATTERN = re.compile(
        r"^(?:§\s*\d+[a-z]?\.|\d+\.)\s+([A-ZА-Я].+)$", re.MULTILINE
    )

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

        Identifies LaTeX environments, section headers, list items, and narrative text.
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
        previous_line: Optional[DocumentLine] = None
        has_recent_level2: bool = False

        for line in lines:
            text = line.text.strip()

            # Check for section headers (LaTeX, Markdown, or book-style)
            # Only check if not inside an environment
            if not env_stack:
                in_narrative_block = (
                    current_block_type == BlockType.NARRATIVE
                    and len(current_block_lines) > 0
                )
                section_info = self._detect_section_header(
                    line, previous_line, in_narrative_block, has_recent_level2
                )

                if section_info:
                    # Section headers flush blocks
                    if current_block_lines:
                        blocks.append(
                            self._create_block(
                                current_block_type or BlockType.NARRATIVE,
                                current_block_lines,
                            )
                        )
                        current_block_lines = []
                        current_block_type = None
                        has_recent_level2 = False

                    # Add section header block
                    blocks.append(self._create_block(BlockType.SECTION_HEADER, [line]))

                    # Track if this is a Level 2 section for next block
                    if section_info["level"] == 2:
                        has_recent_level2 = True
                    else:
                        has_recent_level2 = False

                    previous_line = line
                    continue

                # Check for list items (digit + dot pattern that failed section
                # criteria). Only check if not in narrative block with content
                if not in_narrative_block:
                    list_item_pattern = re.compile(r"^\d+\.\s+")
                    if list_item_pattern.match(text):
                        # This is a list item
                        if current_block_lines:
                            blocks.append(
                                self._create_block(
                                    current_block_type or BlockType.NARRATIVE,
                                    current_block_lines,
                                )
                            )
                            current_block_lines = []
                            current_block_type = None
                            has_recent_level2 = False

                        # Create list item block
                        blocks.append(self._create_block(BlockType.LIST_ITEM, [line]))
                        previous_line = line
                        continue

            # Handle numbered lines in narrative blocks
            # If we're in a narrative block with content, numbered lines are
            # part of narrative
            if (
                not env_stack
                and current_block_type == BlockType.NARRATIVE
                and len(current_block_lines) > 0
            ):
                # Check if it's a numbered line
                numbered_pattern = re.compile(r"^\d+\.\s+")
                if numbered_pattern.match(text):
                    # Add to current narrative block, don't create new block
                    current_block_lines.append(line)
                    previous_line = line
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
                    has_recent_level2 = False
                else:
                    # Already inside an environment - this is nested
                    # Just add line to current block, don't start new block
                    current_block_lines.append(line)
                    env_stack.append(env_name)
                previous_line = line
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
                    has_recent_level2 = False
                previous_line = line
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
                    previous_line = line
                    continue

            # Regular line within current block or narrative
            current_block_lines.append(line)
            if not current_block_type and not env_stack:
                current_block_type = BlockType.NARRATIVE

            # Update previous_line for next iteration
            previous_line = line

        # Flush remaining block
        if current_block_lines:
            blocks.append(
                self._create_block(
                    current_block_type or BlockType.NARRATIVE, current_block_lines
                )
            )

        return blocks

    def _detect_section_header(
        self,
        line: DocumentLine,
        previous_line: Optional[DocumentLine] = None,
        in_narrative_block: bool = False,
        has_recent_level2: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Detect section header in LaTeX, Markdown, or book-style format.

        Uses strict validation rules to distinguish sections from list items.

        Args:
            line: DocumentLine to check.
            previous_line: Previous DocumentLine for context checking.
            in_narrative_block: True if line is inside a narrative block with content.
            has_recent_level2: True if current block already has a Level 2 section.

        Returns:
            Dict with 'level', 'title', and 'style' if detected, None otherwise.
        """
        text = line.text.strip()
        if not text:
            return None

        # Check if previous line ends with colon - definitely a list item
        if self._previous_line_ends_with_colon(previous_line):
            return None

        # Check LaTeX style first (most reliable)
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

        # Check book-style pattern (e.g., "§ 1a. Название" or "1. Портфель")
        book_match = self.BOOK_SECTION_PATTERN.match(text)
        if not book_match:
            return None

        # Extract title from match
        title = book_match.group(1).strip()

        # Strict header validation rules
        word_count = self._count_words(text)
        if word_count > 15:
            # Headers are concise - reject if too long
            return None

        # Check if starts with § symbol
        starts_with_section = text.strip().startswith("§")

        if starts_with_section:
            # § lines are Level 1 (Global) - always accept if passes word count
            return {
                "level": 1,
                "title": title,
                "style": "book",
            }

        # Numbered lines ("1.", "2.", etc.) - Level 2 (Sub-section) with
        # strict conditions
        # Only accept if:
        # 1. line_type != "text" OR not in continuous paragraph
        # 2. NOT in narrative block with existing content
        # 3. NOT has_recent_level2 in same block
        # 4. Previous line doesn't end with colon (already checked above)

        # Check if line is part of continuous paragraph
        is_continuous = self._is_continuous_paragraph(line, previous_line)

        # Condition 1: line_type != "text" OR not in continuous paragraph
        if line.line_type == "text" and is_continuous:
            return None

        # Condition 2: NOT in narrative block with existing content
        if in_narrative_block:
            return None

        # Condition 3: NOT has_recent_level2 in same block
        if has_recent_level2:
            return None

        # All conditions passed - this is a Level 2 section
        return {
            "level": 2,
            "title": title,
            "style": "book",
        }

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

    def _count_words(self, text: str) -> int:
        """Count words in text.

        Args:
            text: Text to count words in.

        Returns:
            Number of words (split on whitespace, filtered empty strings).
        """
        if not text:
            return 0
        words = [w for w in text.split() if w.strip()]
        return len(words)

    def _previous_line_ends_with_colon(
        self, previous_line: Optional[DocumentLine]
    ) -> bool:
        """Check if previous line ends with colon.

        Args:
            previous_line: Previous DocumentLine or None.

        Returns:
            True if previous line text ends with colon, False otherwise.
        """
        if not previous_line or not previous_line.text:
            return False
        return previous_line.text.strip().endswith(":")

    def _is_continuous_paragraph(
        self, line: DocumentLine, previous_line: Optional[DocumentLine]
    ) -> bool:
        """Check if line appears to be part of continuous paragraph.

        Args:
            line: Current line to check.
            previous_line: Previous DocumentLine or None.

        Returns:
            True if line is part of continuous paragraph, False otherwise.
        """
        # If line_type is not "text", it's not a continuous paragraph
        if line.line_type != "text":
            return False

        # If no previous line, it's not continuous
        if not previous_line:
            return False

        # Check if previous line ends with sentence-ending punctuation
        prev_text = previous_line.text.strip()
        if not prev_text:
            return False

        # Sentence-ending punctuation: period, exclamation, question mark
        sentence_endings = ".!?"
        # If previous line ends with sentence-ending punctuation, it's not continuous
        if prev_text[-1] in sentence_endings:
            return False

        # If previous line ends with lowercase letter or comma, likely continuous
        last_char = prev_text[-1]
        if last_char.islower() or last_char == ",":
            return True

        return False

    def _create_block(self, block_type: BlockType, lines: List[DocumentLine]) -> Block:
        """Create Block from list of lines.

        Filters out OCR artifacts (1-4 digit lines at start/end of block).

        Args:
            block_type: Type of block.
            lines: Lines comprising the block.

        Returns:
            Block object.
        """
        # Filter out OCR artifacts: lines with only 1-4 digits at start/end
        filtered_lines: List[DocumentLine] = []
        for i, line in enumerate(lines):
            # Skip if first or last line and it's only 1-4 digits
            if (i == 0 or i == len(lines) - 1) and re.match(
                r"^\d{1,4}$", line.text.strip()
            ):
                continue
            filtered_lines.append(line)

        # If all lines were filtered, keep at least one (shouldn't happen, but safety)
        if not filtered_lines:
            filtered_lines = lines[:1]

        text = "\n".join(line.text for line in filtered_lines)
        return Block(
            block_type=block_type,
            text=text,
            start_line_id=filtered_lines[0].id,
            end_line_id=filtered_lines[-1].id,
            start_page=filtered_lines[0].page_number,
            end_page=filtered_lines[-1].page_number,
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

        Respects section boundaries, size limits, and page boundaries.
        Merges list items together into narrative chunks.

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

            # Handle list items - allow merging with other list items or small
            # narrative blocks
            if block.block_type == BlockType.LIST_ITEM:
                if current_merge and (
                    current_merge[-1].block_type == BlockType.LIST_ITEM
                    or (
                        current_merge[-1].block_type == BlockType.NARRATIVE
                        and current_tokens < self.MIN_TOKENS
                    )
                ):
                    # Merge with existing list items or small narrative
                    current_merge.append(block)
                    current_tokens += block_tokens
                    continue
                else:
                    # Start new merge or flush current if too large
                    if current_merge:
                        merged.append(self._merge_block_list(current_merge))
                        current_merge = []
                        current_tokens = 0
                    # Start new merge with this list item
                    current_merge = [block]
                    current_tokens = block_tokens
                    continue

            # Check if adding this block would cross a page boundary
            # If we already have enough tokens, flush before crossing
            if (
                current_merge
                and block.start_page > current_merge[-1].end_page
                and current_tokens >= self.MIN_TOKENS
            ):
                # Flush current merge before crossing page boundary
                merged.append(self._merge_block_list(current_merge))
                current_merge = []
                current_tokens = 0

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

        Converts merged list items to NARRATIVE to prevent fragmentation.

        Args:
            blocks: Blocks to merge.

        Returns:
            Single merged block.
        """
        if len(blocks) == 1:
            return blocks[0]

        # If all blocks are list items, convert to NARRATIVE
        if all(b.block_type == BlockType.LIST_ITEM for b in blocks):
            return Block(
                block_type=BlockType.NARRATIVE,
                text="\n\n".join(b.text for b in blocks),
                start_line_id=blocks[0].start_line_id,
                end_line_id=blocks[-1].end_line_id,
                start_page=blocks[0].start_page,
                end_page=blocks[-1].end_page,
            )

        # Use first non-narrative, non-list-item type if available
        block_type = blocks[0].block_type
        for b in blocks:
            if b.block_type not in (BlockType.NARRATIVE, BlockType.LIST_ITEM):
                block_type = b.block_type
                break
        # If we only have narrative/list items, use narrative
        if block_type == BlockType.LIST_ITEM:
            block_type = BlockType.NARRATIVE

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
                # Create a minimal DocumentLine-like object for section detection
                # For already-parsed section headers, we use lenient detection
                class MinimalLine:
                    def __init__(self, text: str):
                        self.text = text
                        self.line_type = "section_header"

                minimal_line = MinimalLine(block.text)
                section_info = self._detect_section_header(minimal_line)
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
