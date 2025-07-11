from typing import Annotated
import typer
import pathlib
import sys
from rich import print
import importlib.util

from smk.build import BuildConfig, BuildError, BuildType, pull_target

project_root = pathlib.Path.cwd()

def load_build():
    build_path    = project_root / "build.py"
    if not build_path.exists():
        raise BuildError("No build.py in this project")
    spec = importlib.util.spec_from_file_location("_user_build", build_path)
    if not spec:
        raise BuildError("build.py can't be loaded")
    mod  = importlib.util.module_from_spec(spec)

    sys.modules[spec.name] = mod
    loader = spec.loader
    if not loader:
        raise BuildError("build.py can't be executed")
    loader.exec_module(mod)

    
def import_user_target() -> BuildConfig:
    load_build()
    try:
        return next(pull_target())
    except:
        print(f"[red bold]No targets found[/]")
        sys.exit(1)



app = typer.Typer()


@app.command()
def build(
        generate_db: Annotated[
            bool,
            typer.Option("-c",help="Generate compile-commands.json")
        ] = False,
        verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Verbose output")] = False,
        run: Annotated[bool, typer.Option("--run", "-r", help="Run built executable")] = False,
        build_type: Annotated[BuildType, typer.Option("--type", "-t", help="Build type")] = BuildType.Debug,
):
    """Build executable"""
    target = import_user_target()
    target.build(generate_db, verbose, build_type)
    if run:
        target.run()


@app.command()
def clean():
    """Clean build directory"""
    target = import_user_target()
    target.clean()


if __name__ == "__main__":
    app()
