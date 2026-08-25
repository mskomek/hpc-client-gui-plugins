"""A completely ordinary Python script with nothing Ansys-related."""

import sys


def fibonacci(limit: int) -> list[int]:
    values = [0, 1]
    while len(values) < limit:
        values.append(values[-1] + values[-2])
    return values


def main() -> int:
    for value in fibonacci(10):
        print(value)
    return 0


if __name__ == "__main__":
    sys.exit(main())
