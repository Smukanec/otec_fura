from pathlib import Path
import tomllib


def main() -> None:
    """Sync requirements.txt with project dependencies."""
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())
    deps = pyproject.get("project", {}).get("dependencies", [])
    deps = sorted(deps)
    content = "# Mirror of dependencies defined in pyproject.toml\n" + "\n".join(deps) + "\n"
    Path("requirements.txt").write_text(content)


if __name__ == "__main__":
    main()
