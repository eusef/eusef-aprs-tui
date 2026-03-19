"""Tests for aprs_tui.map.braille_canvas — BrailleCanvas core class."""
from __future__ import annotations

from rich.style import Style
from rich.text import Text

from aprs_tui.map.braille_canvas import BrailleCanvas
from aprs_tui.map.styles import FEATURE_STYLES, get_style


class TestCanvasCreation:
    def test_dimensions(self):
        c = BrailleCanvas(10, 5)
        assert c.width == 20
        assert c.height == 20
        assert c.char_width == 10
        assert c.char_height == 5

    def test_zero_size(self):
        c = BrailleCanvas(0, 0)
        assert c.width == 0
        assert c.height == 0
        assert c.render() == []

    def test_single_cell(self):
        c = BrailleCanvas(1, 1)
        assert c.width == 2
        assert c.height == 4

    def test_initial_state_is_blank(self):
        c = BrailleCanvas(3, 2)
        lines = c.render()
        assert len(lines) == 2
        for line in lines:
            assert len(line) == 3
            assert all(ch == "\u2800" for ch in line)


class TestSetClearDot:
    def test_set_dot(self):
        c = BrailleCanvas(1, 1)
        c.set_dot(0, 0)
        assert c.get_dot(0, 0) is True
        assert c.get_dot(1, 0) is False

    def test_clear_dot(self):
        c = BrailleCanvas(1, 1)
        c.set_dot(0, 0)
        c.clear_dot(0, 0)
        assert c.get_dot(0, 0) is False

    def test_out_of_bounds_ignored(self):
        c = BrailleCanvas(1, 1)
        # Should not raise
        c.set_dot(-1, 0)
        c.set_dot(0, -1)
        c.set_dot(2, 0)
        c.set_dot(0, 4)
        c.clear_dot(100, 100)
        assert c.get_dot(-1, 0) is False
        assert c.get_dot(100, 100) is False

    def test_all_eight_dots_in_cell(self):
        c = BrailleCanvas(1, 1)
        for x in range(2):
            for y in range(4):
                c.set_dot(x, y)
        # All 8 bits set = 0xFF
        lines = c.render()
        assert lines[0] == chr(0x2800 + 0xFF)

    def test_single_dot_renders_correctly(self):
        """Dot at (0, 0) should set bit 0 → U+2801."""
        c = BrailleCanvas(1, 1)
        c.set_dot(0, 0)
        assert c.render()[0] == chr(0x2801)

    def test_dot_col1_row0(self):
        """Dot at (1, 0) should set bit 3 → U+2808."""
        c = BrailleCanvas(1, 1)
        c.set_dot(1, 0)
        assert c.render()[0] == chr(0x2808)

    def test_dot_col0_row3(self):
        """Dot at (0, 3) should set bit 6 → U+2840."""
        c = BrailleCanvas(1, 1)
        c.set_dot(0, 3)
        assert c.render()[0] == chr(0x2840)

    def test_dot_col1_row3(self):
        """Dot at (1, 3) should set bit 7 → U+2880."""
        c = BrailleCanvas(1, 1)
        c.set_dot(1, 3)
        assert c.render()[0] == chr(0x2880)


class TestDrawLine:
    def test_horizontal_line(self):
        c = BrailleCanvas(5, 1)
        c.draw_line(0, 0, 9, 0)
        for x in range(10):
            assert c.get_dot(x, 0) is True

    def test_vertical_line(self):
        c = BrailleCanvas(1, 3)
        c.draw_line(0, 0, 0, 11)
        for y in range(12):
            assert c.get_dot(0, y) is True

    def test_diagonal_line(self):
        c = BrailleCanvas(3, 3)
        c.draw_line(0, 0, 5, 11)
        assert c.get_dot(0, 0) is True
        assert c.get_dot(5, 11) is True

    def test_single_point(self):
        c = BrailleCanvas(2, 2)
        c.draw_line(1, 1, 1, 1)
        assert c.get_dot(1, 1) is True
        # Only that one dot should be set
        total = sum(c.get_dot(x, y) for x in range(4) for y in range(8))
        assert total == 1

    def test_reverse_direction(self):
        c1 = BrailleCanvas(3, 2)
        c2 = BrailleCanvas(3, 2)
        c1.draw_line(0, 0, 5, 7)
        c2.draw_line(5, 7, 0, 0)
        assert c1.render() == c2.render()


class TestClear:
    def test_clear_resets_all(self):
        c = BrailleCanvas(3, 3)
        for x in range(6):
            for y in range(12):
                c.set_dot(x, y)
        c.clear()
        lines = c.render()
        for line in lines:
            assert all(ch == "\u2800" for ch in line)


class TestFillPolygon:
    def test_fill_rectangle(self):
        """A filled rectangle should set all dots in the rectangular region."""
        c = BrailleCanvas(5, 3)  # 10×12 dot space
        # Rectangle from (1,1) to (6,6)
        points = [(1, 1), (6, 1), (6, 6), (1, 6)]
        c.fill_polygon(points)
        # Interior dots should be set
        for y in range(1, 6):
            for x in range(1, 7):
                assert c.get_dot(x, y) is True, f"dot ({x},{y}) should be set"
        # A dot clearly outside the rectangle should not be set
        assert c.get_dot(0, 0) is False
        assert c.get_dot(9, 11) is False

    def test_fill_triangle(self):
        """A filled triangle should produce a roughly triangular fill."""
        c = BrailleCanvas(5, 3)  # 10×12 dot space
        # Right triangle: (0,0), (8,0), (0,8)
        points = [(0, 0), (8, 0), (0, 8)]
        c.fill_polygon(points)
        # Top-left corner must be filled
        assert c.get_dot(0, 0) is True
        # Along the hypotenuse, interior points should be filled
        assert c.get_dot(1, 1) is True
        # Far corner should not be filled
        assert c.get_dot(9, 11) is False
        # Point well outside the triangle
        assert c.get_dot(7, 7) is False

    def test_fill_concave_l_shape(self):
        """A concave L-shaped polygon must fill only the L region."""
        c = BrailleCanvas(5, 5)  # 10×20 dot space
        # L-shape:
        #  (0,0)---(4,0)
        #    |       |
        #  (0,8)---(2,8)
        #            |
        #          (2,4)---(4,4)
        # Actually let's define a cleaner L:
        #  (0,0) -> (4,0) -> (4,4) -> (2,4) -> (2,8) -> (0,8)
        points = [(0, 0), (4, 0), (4, 4), (2, 4), (2, 8), (0, 8)]
        c.fill_polygon(points)
        # Inside the top part of the L
        assert c.get_dot(1, 1) is True
        assert c.get_dot(3, 1) is True
        # Inside the bottom-left leg of the L
        assert c.get_dot(1, 6) is True
        # Outside the L: bottom-right area
        assert c.get_dot(3, 6) is False

    def test_fill_empty_list(self):
        """Empty point list should be a no-op (no crash)."""
        c = BrailleCanvas(3, 3)
        c.fill_polygon([])
        # Nothing set
        for x in range(6):
            for y in range(12):
                assert c.get_dot(x, y) is False

    def test_fill_single_point(self):
        """Single point should be a no-op."""
        c = BrailleCanvas(3, 3)
        c.fill_polygon([(2, 2)])
        for x in range(6):
            for y in range(12):
                assert c.get_dot(x, y) is False

    def test_fill_two_points(self):
        """Two points (a line segment) should be a no-op."""
        c = BrailleCanvas(3, 3)
        c.fill_polygon([(0, 0), (5, 5)])
        for x in range(6):
            for y in range(12):
                assert c.get_dot(x, y) is False


class TestDrawText:
    def test_text_at_correct_position(self):
        """Text characters appear at the correct char-cell positions."""
        c = BrailleCanvas(10, 3)
        # Place "Hi" at dot position (0, 0) => char col 0, char row 0
        c.draw_text(0, 0, "Hi")
        lines = c.render()
        assert lines[0][0] == "H"
        assert lines[0][1] == "i"
        # Remaining cells are still braille blanks
        assert lines[0][2] == "\u2800"

    def test_text_overrides_braille_dots(self):
        """Text overlay should replace braille characters in the same cell."""
        c = BrailleCanvas(5, 2)
        # Set dots in cells 0, 1, and 2
        c.set_dot(0, 0)  # cell 0
        c.set_dot(2, 0)  # cell 1
        c.set_dot(4, 0)  # cell 2
        # Overlay text on the first two char cells (cells 0 and 1)
        c.draw_text(0, 0, "AB")
        lines = c.render()
        assert lines[0][0] == "A"
        assert lines[0][1] == "B"
        # Third char cell (cell 2, dot col 4) still has its braille dot
        assert lines[0][2] != "\u2800"

    def test_text_out_of_bounds_ignored(self):
        """Characters that map to OOB cells are silently dropped."""
        c = BrailleCanvas(3, 1)  # 3 char columns
        # Start text at dot x=4 => char col 2, so "Hello" extends to col 6
        c.draw_text(4, 0, "Hello")
        lines = c.render()
        # Only char col 2 is in bounds
        assert lines[0][2] == "H"
        # Cols 0 and 1 are untouched
        assert lines[0][0] == "\u2800"
        assert lines[0][1] == "\u2800"

    def test_text_negative_coords_ignored(self):
        """Negative dot coords that map to negative char cells are ignored."""
        c = BrailleCanvas(5, 2)
        # dot x=-2 => char col -1, which is OOB
        c.draw_text(-2, 0, "X")
        lines = c.render()
        for ch in lines[0]:
            assert ch == "\u2800"

    def test_text_on_second_row(self):
        """Text placed at dot y=4 appears on char row 1."""
        c = BrailleCanvas(5, 3)
        c.draw_text(0, 4, "Row1")
        lines = c.render()
        # Row 0 should be blank
        assert all(ch == "\u2800" for ch in lines[0])
        # Row 1 should have the text
        assert lines[1][:4] == "Row1"


class TestClearWithTextOverlay:
    def test_clear_resets_text_overlay(self):
        """clear() must remove text overlay in addition to braille dots."""
        c = BrailleCanvas(5, 2)
        c.set_dot(0, 0)
        c.draw_text(2, 0, "Hi")
        c.clear()
        lines = c.render()
        for line in lines:
            assert all(ch == "\u2800" for ch in line)


class TestRender:
    def test_render_returns_correct_row_count(self):
        c = BrailleCanvas(4, 3)
        assert len(c.render()) == 3

    def test_render_returns_correct_col_count(self):
        c = BrailleCanvas(4, 3)
        lines = c.render()
        for line in lines:
            assert len(line) == 4

    def test_multi_cell_pattern(self):
        """Two dots in different cells render to two different characters."""
        c = BrailleCanvas(2, 1)
        c.set_dot(0, 0)  # cell 0, bit 0
        c.set_dot(2, 0)  # cell 1, bit 0
        lines = c.render()
        assert lines[0][0] == chr(0x2801)
        assert lines[0][1] == chr(0x2801)


class TestRenderRich:
    def test_render_rich_returns_list_of_text(self):
        """render_rich() must return a list of rich.text.Text objects."""
        c = BrailleCanvas(3, 2)
        result = c.render_rich()
        assert len(result) == 2
        for item in result:
            assert isinstance(item, Text)

    def test_render_rich_default_style(self):
        """Cells with no style set should use the default style."""
        c = BrailleCanvas(2, 1)
        c.set_dot(0, 0)
        rows = c.render_rich()
        assert len(rows) == 1
        # The plain text content should match the braille character
        assert rows[0].plain == c.render()[0]

    def test_set_cell_style_applies_correct_color(self):
        """set_cell_style should assign a feature type that render_rich uses."""
        c = BrailleCanvas(3, 1)
        c.set_dot(0, 0)
        c.set_cell_style(0, 0, "water")
        rows = c.render_rich()
        # Extract the style of the first span
        spans = rows[0]._spans
        assert len(spans) >= 1
        # The first character should have the water style
        water_style = get_style("water")
        assert spans[0].style == water_style

    def test_set_region_style_colors_multiple_cells(self):
        """set_region_style should apply the feature type to all cells in the region."""
        c = BrailleCanvas(4, 2)
        # Set dots so we have visible content
        for x in range(8):
            c.set_dot(x, 0)
        # Region from dot (0,0) to dot (5,3) => char cols 0-2, char row 0
        c.set_region_style(0, 0, 5, 3, "highway")
        rows = c.render_rich()
        highway_style = get_style("highway")
        # Check that the first 3 cells in row 0 have the highway style
        spans = rows[0]._spans
        highway_spans = [s for s in spans if s.style == highway_style]
        assert len(highway_spans) == 3

    def test_render_rich_with_text_overlay(self):
        """Text overlay should appear in render_rich output with the cell's style."""
        c = BrailleCanvas(5, 1)
        c.draw_text(0, 0, "Hi")
        c.set_cell_style(0, 0, "label")
        c.set_cell_style(1, 0, "label")
        rows = c.render_rich()
        # The plain text should start with "Hi"
        assert rows[0].plain[:2] == "Hi"
        # Verify at least the label-styled spans are present
        label_style = get_style("label")
        spans = rows[0]._spans
        label_spans = [s for s in spans if s.style == label_style]
        assert len(label_spans) >= 2

    def test_set_cell_style_out_of_bounds_ignored(self):
        """Out-of-bounds set_cell_style should not raise."""
        c = BrailleCanvas(2, 2)
        # Should not raise
        c.set_cell_style(-1, 0, "water")
        c.set_cell_style(0, -1, "water")
        c.set_cell_style(2, 0, "water")
        c.set_cell_style(0, 2, "water")
        # All cells should still be None
        assert all(s is None for s in c._color_buffer)


class TestClearResetsColorBuffer:
    def test_clear_resets_color_buffer(self):
        """clear() must reset the color buffer to all None."""
        c = BrailleCanvas(3, 2)
        c.set_cell_style(0, 0, "water")
        c.set_cell_style(1, 0, "highway")
        c.set_region_style(0, 0, 5, 7, "road")
        c.clear()
        assert all(s is None for s in c._color_buffer)


class TestRenderAscii:
    def test_render_ascii_empty_canvas(self):
        """An empty canvas should render as all spaces."""
        c = BrailleCanvas(4, 3)
        lines = c.render_ascii()
        assert len(lines) == 3
        for line in lines:
            assert len(line) == 4
            assert all(ch == " " for ch in line)

    def test_render_ascii_single_dot(self):
        """A single dot in a cell should render as '.' (generic filled)."""
        c = BrailleCanvas(1, 1)
        c.set_dot(0, 0)
        lines = c.render_ascii()
        assert lines[0] == "."

    def test_render_ascii_full_cell(self):
        """A cell with all 8 dots set should render as '#'."""
        c = BrailleCanvas(1, 1)
        for x in range(2):
            for y in range(4):
                c.set_dot(x, y)
        lines = c.render_ascii()
        assert lines[0] == "#"

    def test_render_ascii_horizontal_line(self):
        """Dots spread horizontally across both columns in the same row(s) → '-'."""
        c = BrailleCanvas(1, 1)
        # Set dots in row 0 across both columns: bits 0 and 3
        c.set_dot(0, 0)
        c.set_dot(1, 0)
        lines = c.render_ascii()
        assert lines[0] == "-"

    def test_render_ascii_vertical_line(self):
        """Dots spread vertically in one column across multiple rows → '|'."""
        c = BrailleCanvas(1, 1)
        # Set dots in col 0, rows 0-3: bits 0,1,2,6
        c.set_dot(0, 0)
        c.set_dot(0, 1)
        c.set_dot(0, 2)
        c.set_dot(0, 3)
        lines = c.render_ascii()
        assert lines[0] == "|"

    def test_render_ascii_text_overlay_takes_priority(self):
        """Text overlay characters should take priority over dot-based ASCII."""
        c = BrailleCanvas(3, 1)
        # Set dots everywhere
        for x in range(6):
            for y in range(4):
                c.set_dot(x, y)
        # Overlay text on the first cell
        c.draw_text(0, 0, "A")
        lines = c.render_ascii()
        assert lines[0][0] == "A"
        # Other cells should still render based on dots
        assert lines[0][1] == "#"
        assert lines[0][2] == "#"

    def test_render_ascii_correct_dimensions(self):
        """render_ascii() should return the same dimensions as render()."""
        c = BrailleCanvas(7, 4)
        ascii_lines = c.render_ascii()
        braille_lines = c.render()
        assert len(ascii_lines) == len(braille_lines)
        for a, b in zip(ascii_lines, braille_lines):
            assert len(a) == len(b)


class TestStyles:
    def test_get_style_returns_correct_for_known_types(self):
        """get_style should return the expected style for each known feature type."""
        assert get_style("water") == Style(color="blue")
        assert get_style("highway") == Style(color="yellow")
        assert get_style("station_rf") == Style(color="green", bold=True)
        assert get_style("station_emergency") == Style(color="red", bold=True, blink=True)
        assert get_style("track") == Style(color="cyan", dim=True)
        assert get_style("coastline") == Style(color="bright_blue")
        assert get_style("boundary") == Style(color="white", dim=True)
        assert get_style("station_own") == Style(reverse=True)

    def test_get_style_returns_default_for_unknown(self):
        """Unknown feature types should fall back to the default style."""
        default = FEATURE_STYLES["default"]
        assert get_style("totally_unknown_feature") == default
        assert get_style("") == default
        assert get_style("nonexistent") == default
