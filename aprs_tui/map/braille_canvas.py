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

from rich.text import Text

from aprs_tui.map.styles import get_style


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
        # Parallel to _cells: stores feature type string per cell for coloring.
        self._color_buffer: list[str | None] = [None] * (char_width * char_height)
        # Text overlay: maps (char_col, char_row) → single character.
        self._text_overlay: dict[tuple[int, int], str] = {}

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

    def fill_polygon(self, points: list[tuple[int, int]]) -> None:
        """Fill a polygon using the scanline algorithm.

        Args:
            points: List of ``(x, y)`` tuples in braille dot coordinates
                    defining a closed polygon.  Fewer than 3 points is a no-op.

        Handles concave polygons correctly via the even-odd rule.
        """
        if len(points) < 3:
            return

        ys = [p[1] for p in points]
        min_y = max(min(ys), 0)
        max_y = min(max(ys), self.height - 1)
        n = len(points)

        for y in range(min_y, max_y + 1):
            # Collect x-intersections of every edge with this scanline.
            intersections: list[float] = []
            for i in range(n):
                x0, y0 = points[i]
                x1, y1 = points[(i + 1) % n]

                # Skip horizontal edges.
                if y0 == y1:
                    continue

                # Ensure y0 < y1 for consistent handling.
                if y0 > y1:
                    x0, y0, x1, y1 = x1, y1, x0, y0

                # Edge spans [y0, y1).  Exclude the top endpoint to avoid
                # double-counting at vertices shared by two edges.
                if y0 <= y < y1:
                    t = (y - y0) / (y1 - y0)
                    ix = x0 + t * (x1 - x0)
                    intersections.append(ix)

            intersections.sort()

            # Fill between pairs of intersections (even-odd rule).
            for j in range(0, len(intersections) - 1, 2):
                x_start = int(intersections[j] + 0.5)
                x_end = int(intersections[j + 1] + 0.5)
                x_start = max(x_start, 0)
                x_end = min(x_end, self.width - 1)
                for x in range(x_start, x_end + 1):
                    self.set_dot(x, y)

    def fill_polygon_style(
        self, points: list[tuple[int, int]], feature_type: str
    ) -> None:
        """Fill a polygon's interior with a background style (no dots).

        Uses the same scanline algorithm as :meth:`fill_polygon` but writes
        to the color buffer instead of setting braille dots.  This produces
        clean colored backgrounds for features like water.
        """
        if len(points) < 3:
            return

        ys = [p[1] for p in points]
        min_y = max(min(ys), 0)
        max_y = min(max(ys), self.height - 1)
        n = len(points)

        for y in range(min_y, max_y + 1):
            intersections: list[float] = []
            for i in range(n):
                x0, y0 = points[i]
                x1, y1 = points[(i + 1) % n]
                if y0 == y1:
                    continue
                if y0 > y1:
                    x0, y0, x1, y1 = x1, y1, x0, y0
                if y0 <= y < y1:
                    t = (y - y0) / (y1 - y0)
                    ix = x0 + t * (x1 - x0)
                    intersections.append(ix)

            intersections.sort()

            char_row = y // 4
            for j in range(0, len(intersections) - 1, 2):
                x_start = int(intersections[j] + 0.5)
                x_end = int(intersections[j + 1] + 0.5)
                x_start = max(x_start, 0)
                x_end = min(x_end, self.width - 1)
                col_start = x_start // 2
                col_end = x_end // 2
                for c in range(col_start, min(col_end + 1, self._char_width)):
                    if 0 <= c < self._char_width and 0 <= char_row < self._char_height:
                        self._color_buffer[char_row * self._char_width + c] = feature_type

    def draw_text(self, x: int, y: int, text: str) -> None:
        """Render ASCII text at a braille-coordinate position.

        Each character occupies a 2-wide by 4-tall braille dot cell.
        Characters that map to out-of-bounds character cells are silently
        ignored.

        Args:
            x: Horizontal position in braille dot coordinates.
            y: Vertical position in braille dot coordinates.
            text: String to render.
        """
        char_col = x // 2
        char_row = y // 4
        for i, ch in enumerate(text):
            col = char_col + i
            if 0 <= col < self._char_width and 0 <= char_row < self._char_height:
                self._text_overlay[(col, char_row)] = ch

    # ------------------------------------------------------------------
    # Canvas operations
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Reset all dots, text overlay, and color buffer to blank."""
        for i in range(len(self._cells)):
            self._cells[i] = 0
        self._color_buffer = [None] * len(self._cells)
        self._text_overlay.clear()

    # ------------------------------------------------------------------
    # Style management
    # ------------------------------------------------------------------

    def set_cell_style(self, char_col: int, char_row: int, feature_type: str) -> None:
        """Set the feature type (for coloring) of a character cell.

        Out-of-bounds coordinates are silently ignored.
        """
        if (
            char_col < 0
            or char_row < 0
            or char_col >= self._char_width
            or char_row >= self._char_height
        ):
            return
        self._color_buffer[char_row * self._char_width + char_col] = feature_type

    def set_region_style(
        self, x0: int, y0: int, x1: int, y1: int, feature_type: str
    ) -> None:
        """Set the feature type on a rectangular region (in dot coordinates).

        The dot coordinates are converted to character-cell coordinates and
        every cell touched by the rectangle is assigned *feature_type*.
        """
        # Convert dot coords to inclusive char-cell range.
        col0 = max(x0 // 2, 0)
        row0 = max(y0 // 4, 0)
        col1 = min(x1 // 2, self._char_width - 1)
        row1 = min(y1 // 4, self._char_height - 1)
        for r in range(row0, row1 + 1):
            for c in range(col0, col1 + 1):
                self._color_buffer[r * self._char_width + c] = feature_type

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render_rich(self) -> list[Text]:
        """Convert dot buffer to a list of :class:`rich.text.Text` with color styling.

        Each :class:`Text` object corresponds to one row of terminal characters.
        Text overlay characters replace the braille character in their cell.
        Cells with no style set use the ``"default"`` style.
        """
        rows: list[Text] = []
        for row in range(self._char_height):
            line = Text()
            start = row * self._char_width
            for col in range(self._char_width):
                idx = start + col
                feature = self._color_buffer[idx]
                style = get_style(feature) if feature else get_style("default")
                key = (col, row)
                if key in self._text_overlay:
                    line.append(self._text_overlay[key], style=style)
                else:
                    line.append(chr(0x2800 + self._cells[idx]), style=style)
            rows.append(line)
        return rows

    def render(self) -> list[str]:
        """Convert dot buffer to a list of Unicode braille character strings.

        Each string corresponds to one row of terminal characters.
        Text overlay characters replace the braille character in their cell.
        """
        lines: list[str] = []
        for row in range(self._char_height):
            start = row * self._char_width
            chars: list[str] = []
            for col in range(self._char_width):
                key = (col, row)
                if key in self._text_overlay:
                    chars.append(self._text_overlay[key])
                else:
                    chars.append(chr(0x2800 + self._cells[start + col]))
            lines.append("".join(chars))
        return lines

    def render_ascii(self) -> list[str]:
        """Render as ASCII characters instead of braille.

        Each character cell that has ANY dots set renders as a context-dependent
        ASCII character. Cells with no dots render as space. Text overlay
        characters take priority (same as render()).

        This is a simpler, lower-resolution fallback for terminals that don't
        support Unicode braille.
        """
        lines: list[str] = []
        for row in range(self._char_height):
            start = row * self._char_width
            chars: list[str] = []
            for col in range(self._char_width):
                key = (col, row)
                if key in self._text_overlay:
                    chars.append(self._text_overlay[key])
                else:
                    cell = self._cells[start + col]
                    chars.append(self._cell_to_ascii(cell))
            lines.append("".join(chars))
        return lines

    @staticmethod
    def _cell_to_ascii(cell: int) -> str:
        """Convert an 8-bit braille cell pattern to an ASCII character.

        Heuristic:
        - 0x00 (no dots)       → " "
        - 0xFF (all 8 dots)    → "#"
        - Otherwise, classify by dot distribution across columns/rows.
        """
        if cell == 0:
            return " "
        if cell == 0xFF:
            return "#"

        # Count dots in left column (bits 0,1,2,6) vs right column (bits 3,4,5,7)
        left = 0
        for bit in (0, 1, 2, 6):
            if cell & (1 << bit):
                left += 1
        right = 0
        for bit in (3, 4, 5, 7):
            if cell & (1 << bit):
                right += 1

        # Count dots in top rows (rows 0-1: bits 0,3,1,4) vs bottom rows (rows 2-3: bits 2,5,6,7)
        top = 0
        for bit in (0, 3, 1, 4):
            if cell & (1 << bit):
                top += 1
        bottom = 0
        for bit in (2, 5, 6, 7):
            if cell & (1 << bit):
                bottom += 1

        total = left + right

        # Diagonal detection:
        # Top-left to bottom-right: bits in top-left (0,1) and bottom-right (5,7)
        tl = 0
        for bit in (0, 1):
            if cell & (1 << bit):
                tl += 1
        br = 0
        for bit in (5, 7):
            if cell & (1 << bit):
                br += 1
        # Bottom-left to top-right: bits in top-right (3,4) and bottom-left (2,6)
        tr = 0
        for bit in (3, 4):
            if cell & (1 << bit):
                tr += 1
        bl = 0
        for bit in (2, 6):
            if cell & (1 << bit):
                bl += 1

        diag_backslash = tl + br  # top-left + bottom-right
        diag_slash = tr + bl  # top-right + bottom-left

        # Cross-like: both horizontal and vertical presence is strong
        has_horizontal = (left > 0 and right > 0) and (top >= 1 or bottom >= 1)
        has_vertical = (top > 0 and bottom > 0) and (left >= 1 or right >= 1)

        if has_horizontal and has_vertical and total >= 4:
            return "+"

        # Strong horizontal: dots spread across both columns, concentrated in few rows
        if left > 0 and right > 0 and abs(top - bottom) >= abs(left - right):
            if top > bottom + 1 or bottom > top + 1:
                pass  # not convincingly horizontal
            elif left > 0 and right > 0:
                # Check diagonal bias
                if diag_backslash > diag_slash + 1:
                    return "\\"
                if diag_slash > diag_backslash + 1:
                    return "/"
                return "-"

        # Strong vertical: dots concentrated in one column
        if top > 0 and bottom > 0 and abs(left - right) > abs(top - bottom):
            return "|"

        # Diagonal checks
        if diag_backslash >= 3 and diag_backslash > diag_slash + 1:
            return "\\"
        if diag_slash >= 3 and diag_slash > diag_backslash + 1:
            return "/"

        # Vertical bias
        if abs(left - right) > abs(top - bottom) and (top > 0 and bottom > 0):
            return "|"

        # Horizontal bias
        if left > 0 and right > 0:
            return "-"

        # Default: generic filled
        return "."
