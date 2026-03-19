"""Tests for aprs_tui.map.braille_canvas — BrailleCanvas core class."""
from __future__ import annotations

from aprs_tui.map.braille_canvas import BrailleCanvas


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
