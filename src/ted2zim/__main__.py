import pathlib
import sys


def main():
    # allows running it from source using python ted2zim
    sys.path = [str(pathlib.Path(__file__).parent.parent.resolve()), *sys.path]

    from ted2zim.entrypoint import main as entry

    entry()


if __name__ == "__main__":
    main()
