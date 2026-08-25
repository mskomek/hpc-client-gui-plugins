"""Line/column utilities shared by every dialect parser."""

from __future__ import annotations


class LineIndex:
    """0-based offset <-> 1-based line / 1-based column mapping."""

    __slots__ = ("_text", "_line_starts")

    def __init__(self, text: str) -> None:
        self._text = text
        starts = [0]
        for index, char in enumerate(text):
            if char == "\n":
                starts.append(index + 1)
        self._line_starts = starts

    @property
    def line_count(self) -> int:
        return len(self._line_starts)

    def line_text(self, line: int) -> str:
        """Return the 1-based ``line`` without its trailing newline."""
        start, end = self.line_span(line)
        return self._text[start:end]

    def line_span(self, line: int) -> tuple[int, int]:
        if line < 1 or line > len(self._line_starts):
            raise IndexError(f"line {line} out of range")
        start = self._line_starts[line - 1]
        if line < len(self._line_starts):
            end = self._line_starts[line] - 1  # strip the newline
        else:
            end = len(self._text)
            while end > start and self._text[end - 1] == "\r":
                end -= 1
        return start, end

    def line_col(self, offset: int) -> tuple[int, int]:
        """Map a 0-based character offset to (line, column), both 1-based."""
        if offset < 0 or offset > len(self._text):
            offset = min(max(offset, 0), len(self._text))
        low, high = 0, len(self._line_starts) - 1
        while low < high:
            mid = (low + high + 1) // 2
            if self._line_starts[mid] <= offset:
                low = mid
            else:
                high = mid - 1
        return low + 1, offset - self._line_starts[low] + 1

    def offset(self, line: int, column: int) -> int:
        """Map 1-based (line, column) to a 0-based offset."""
        start, end = self.line_span(line)
        return min(start + max(column - 1, 0), end)


def iter_lines(text: str) -> list[str]:
    """Split into lines keeping no terminators (handles \\r\\n)."""
    return text.splitlines()
