"""BrailleCanvas — 2D dot buffer rendered as Unicode braille characters.

Each terminal character cell maps to a 2×4 braille dot grid (U+2800–U+28FF),
yielding 2× horizontal and 4× vertical sub-character resolution.

Dot-to-bit mapping within a braille character:

    Col 0   Col 1
    ─────   ─────
    bit 0   bit 3   row 0
    bit 1   bit 4   row 1
    bit 2   bit 5   row 2
    bit 6   bit 7   row 3
"""
from __future__ import annotations


# Pre-computed lookup: (col, row) within a 2×4 cell → bit index.
_DOT_BIT: list[list[int]] = [
    # col 0        col 1
    [0, 3],  # row 0
    [1, 4],  # row 1
    [2, 5],  # row 2
    [6, 7],  # row 3
]


class BrailleCanvas:
    """2D canvas that renders to Unicode braille characters."""

    def __init__(self, char_width: int, char_height: int) -> None:
        """Create a canvas.

        Args:
            char_width:  Width in terminal character columns.
            char_height: Height in terminal character rows.

        The effective dot resolution is ``(char_width * 2, char_height * 4)``.
        """
        if char_width < 0 or char_height < 0:
            char_width = max(char_width, 0)
            char_height = max(char_height, 0)
        self._char_width = char_width
        self._char_height = char_height
        # Each cell stores an 8-bit pattern for one braille character.
        self._cells = bytearray(char_width * char_height)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def width(self) -> int:
        """Width in braille dots."""
        return self._char_width * 2

    @property
    def height(self) -> int:
        """Height in braille dots."""
        return self._char_height * 4

    @property
    def char_width(self) -> int:
        return self._char_width

    @property
    def char_height(self) -> int:
        return self._char_height

    # ------------------------------------------------------------------
    # Dot manipulation
    # ------------------------------------------------------------------

    def _resolve(self, x: int, y: int) -> tuple[int, int] | None:
        """Map dot (x, y) to (cell_index, bit_index), or None if OOB."""
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return None
        char_col = x // 2
        char_row = y // 4
        dot_col = x % 2
        dot_row = y % 4
        cell_idx = char_row * self._char_width + char_col
        bit_idx = _DOT_BIT[dot_row][dot_col]
        return cell_idx, bit_idx

    def set_dot(self, x: int, y: int) -> None:
        """Set a single braille dot.  Out-of-bounds coordinates are ignored."""
        pos = self._resolve(x, y)
        if pos is not None:
            self._cells[pos[0]] |= 1 << pos[1]

    def clear_dot(self, x: int, y: int) -> None:
        """Clear a single braille dot.  Out-of-bounds coordinates are ignored."""
        pos = self._resolve(x, y)
        if pos is not None:
            self._cells[pos[0]] &= ~(1 << pos[1])

    def get_dot(self, x: int, y: int) -> bool:
        """Return whether a dot is set."""
        pos = self._resolve(x, y)
        if pos is None:
            return False
        return bool(self._cells[pos[0]] & (1 << pos[1]))

    # ------------------------------------------------------------------
    # Drawing primitives
    # ------------------------------------------------------------------

    def draw_line(self, x0: int, y0: int, x1: int, y1: int) -> None:
        """Draw a line using Bresenham's algorithm."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy

        while True:
            self.set_dot(x0, y0)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    # ------------------------------------------------------------------
    # Canvas operations
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Reset all dots to blank."""
        for i in range(len(self._cells)):
            self._cells[i] = 0

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self) -> list[str]:
        """Convert dot buffer to a list of Unicode braille character strings.

        Each string corresponds to one row of terminal characters.
        """
        lines: list[str] = []
        for row in range(self._char_height):
            start = row * self._char_width
            end = start + self._char_width
            lines.append(
                "".join(chr(0x2800 + b) for b in self._cells[start:end])
            )
        return lines
