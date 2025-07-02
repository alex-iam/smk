from typing import Annotated
import typer
import subprocess
import importlib.util
import pathlib
import sys

project_root = pathlib.Path.cwd()

def import_user_target():
    build_path    = project_root / "build.py"
    if not build_path.exists():
        sys.exit("No build.py found in project root.")
    spec = importlib.util.spec_from_file_location("_user_build", build_path)
    mod  = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)          # executes build.py, creating `exe`
    try:
        exe = getattr(mod, "exe")
    except AttributeError:
        sys.exit("build.py must define a top-level variable named 'exe'.")

    if not callable(getattr(exe, "build", None)):
        sys.exit("'exe' must have a .build() method.")
    return exe
    

app = typer.Typer()


@app.command()
def build(
        generate_db: Annotated[
            bool,
            typer.Option("-c",help="Generate compile-commands.json")
        ] = False,
        verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Verbose output")] = False,
):
    """Build executable"""
    _ = import_user_target().build(generate_db, verbose)


@app.command()
def run():
    """Build and run"""
    target = import_user_target()
    target.build()
    target.run()
    


@app.command()
def clean():
    """Clean build directory"""
    target = import_user_target()
    target.clean()


if __name__ == "__main__":
    app()
