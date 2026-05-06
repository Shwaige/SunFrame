from ygmc.cli import handle_sign


if __name__ == "__main__":
    raise SystemExit(handle_sign(__import__("sys").argv[1:]))