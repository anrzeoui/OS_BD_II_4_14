"""Run: python -m src.cli 1048576 [--file examples/book.txt]."""
import argparse
from pathlib import Path
from .allocator import Allocator, AllocationError, execute


def main():
    parser = argparse.ArgumentParser(description="Contiguous memory allocation")
    parser.add_argument("total", type=int)
    parser.add_argument("--file", type=Path, help="UTF-8 command script")
    args = parser.parse_args()
    try:
        model = Allocator(args.total)
    except AllocationError as exc:
        parser.error(str(exc))
    if args.file:
        try:
            commands = args.file.read_text(encoding="utf-8-sig").splitlines()
        except OSError as exc:
            parser.error(str(exc))
    else:
        commands = None
    failed = False
    def run(command):
        nonlocal failed
        try:
            message, stop = execute(model, command)
            print(message)
            return stop
        except AllocationError as exc:
            failed = True
            print(f"ERROR: {exc}")
            return False
    if commands is not None:
        for line in commands:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            print(f"allocator>{line}")
            if run(line):
                break
    else:
        while True:
            try:
                command = input("allocator>")
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if run(command):
                break
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
