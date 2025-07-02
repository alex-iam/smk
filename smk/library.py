from dataclasses import dataclass
import os
import subprocess
import sys
from rich.console import Console


console = Console()

@dataclass
class Library:
    name: str
    cflags: list[str]
    libs: list[str]


def get_local_library(name: str, path: str, static: bool) -> Library:
    """
    Create a Library object for a locally built dependency.
    """
    if not os.path.isdir(path):
        raise FileNotFoundError(f"The specified library path does not exist: '{path}'")

    expected_header = f"{name}.h"
    header_path = os.path.join(path, expected_header)
    if not os.path.exists(header_path):
        raise FileNotFoundError(
            f"Could not find required header '{expected_header}' in directory '{path}'"
        )

    lib_filename = f"lib{name}.a" if static else f"lib{name}.so"

    lib_path = os.path.join(path, lib_filename)

    if not os.path.exists(lib_path):
        raise FileNotFoundError(
            f"Could not find library file '{lib_filename}' in directory '{path}'"
        )

    console.print(f"[green]Found library (local): [bold]{name}[/][/]")

    cflags = ["-I", path]
    
    libs = [f"-L{path}", f"-l{name}"]
    
    return Library(name=name, cflags=cflags, libs=libs)



def get_system_library(name: str, static: bool = False) -> Library:
    """Get cflags and libs for a system library using pkg-config"""
    try:
        cf = subprocess.run(
            ["pkg-config", "--cflags", name],
            capture_output=True,
            text=True,
        ).stdout.split()
        lds = subprocess.run(
            [
                "pkg-config",
                "--libs",
                "--static" if static else "",
                name
            ],
            capture_output=True,
            text=True,
        ).stdout.split()
        console.print(f"[green]Found library (static): [bold]{name}[/][/]")
        return Library(cflags=cf, libs=lds, name=name)
    except subprocess.CalledProcessError as e:
        console.print(f"[red bold]Error: Could not find library '{name}' using pkg-config.[/]")
        console.print(f"[red]Stderr: {e.stderr.strip()}[/]")
        sys.exit(1)
