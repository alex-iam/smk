from collections.abc import Iterator
import concurrent.futures
from dataclasses import dataclass, field
from enum import StrEnum, auto
import shutil
import subprocess
import os
import json
from pathlib import Path
from typing_extensions import override
from rich.table import Table
from rich.console import Console
from rich.panel import Panel

from smk.library import Library


# TODO:
# - Target should be registered explicitly, not inferred by name DONE
# - Separate package DONE
# - Guix package DONE
# - Guix build system
# - Separate configure step
# - Build type DONE
# - Test step
# - Unit tests
# - Install step

console = Console()


class BuildType(StrEnum):
    Debug = auto()
    Release = auto()


class CompilationError(Exception):
    pass


class BuildError(Exception):
    pass


@dataclass
class CompilationResult:
    obj_path: str
    cdb_entry: dict[str, str|list[str]]
    success: bool

    
__TARGET_REGISTRY: list["BuildConfig"] = []


def register_target(target: "BuildConfig"):
    if len(__TARGET_REGISTRY) > 0:
        console.print("[red]Multiple targets are not supported[/]")
        return
    if target not in __TARGET_REGISTRY:
        __TARGET_REGISTRY.append(target)
        console.print(f"[yellow]Target {target.app_name} registered[/]")
    else:
        console.print("[red]One target can only be registered once[/]")


def pull_target() -> Iterator["BuildConfig"]:
    while len(__TARGET_REGISTRY) > 0:
        yield __TARGET_REGISTRY.pop()
    raise StopIteration()



@dataclass
class BuildConfig:
    app_name: str
    root_dir: str

    compiler: str
    
    sources: list[str]
    cflags: list[str]
    libs: list[str] = field(default_factory=list)
    _build_dir: Path = Path("build")
    build_type: BuildType = BuildType.Debug
    
    _verbose: bool = False


    @override
    def __eq__(self, value: object, /) -> bool:
        return self.app_name == value

    def __post_init__(self):
        console.print("Build initialized")
        table = Table(title="Summary", show_header=False)
        table.add_column("Name")
        table.add_column("Value")
        table.add_row("App name", f"[green]{self.app_name}[/]")
        table.add_row("Compiler", f"[green]{self.compiler}[/]")
        # table.add_row("Build type", f"[green]{self.build_type.value}[/]")
        # table.add_row("Build folder", f"[green]./{self._build_dir}[/]")
        console.print(table)
        

    def add_import(self, import_path: str) -> None:
        self.cflags.insert(0, import_path)
        self.cflags.insert(0, "-I")

    def link_library(self, library: Library) -> None:
        self.cflags.extend(library.cflags)
        self.libs.extend(library.libs)

    def __need_recompile(self, obj_path: str, dep_path: str) -> bool:
        res = True
        # Means, not first time compiling
        if os.path.exists(obj_path) and os.path.exists(dep_path):
            obj_mtime = os.path.getmtime(obj_path)

            with open(dep_path, 'r') as f:
                dependencies = f.read().split(': ')[1].replace('\\\n', '').split()

            # any dependency is newer than the object file
            return any(os.path.getmtime(dep) > obj_mtime for dep in dependencies)

        return res

    def compile_file(self, source: str) -> CompilationResult:
        obj_path = os.path.join(self._build_dir, os.path.basename(source) + ".o")
        dep_path = os.path.join(self._build_dir, os.path.basename(source) + ".d")

        os.makedirs(os.path.dirname(obj_path), exist_ok=True)

        cmd = [
            self.compiler,
            *self.cflags,
            "-MMD", "-MF", dep_path, # dependencies for correct skips
            "-c", source,
            "-o", obj_path,
        ]

        cdb_entry = {
            "directory": self.root_dir,
            "arguments": cmd,
            "file": source,
        }

        if not self.__need_recompile(obj_path, dep_path):
            console.print(f"[yellow]{obj_path} is up to date. Skipping...[/]")
            return CompilationResult(obj_path, cdb_entry, True)
        try:
            console.print(f"[yellow]Compiling {source}...[/]")
            if self._verbose:
                console.print(f"Compile command: {' '.join(cmd)}")
            _ = subprocess.run(
                cmd, check=True, capture_output=True, text=True,
            )
            return CompilationResult(obj_path, cdb_entry, True)
        except subprocess.CalledProcessError as e:
            console.print(f"[red bold]Error compiling {source}:[/]")
            console.print(Panel(e.stdout + e.stderr, border_style="red"))
            return CompilationResult(obj_path, cdb_entry, False)

    def compile(self) -> list[CompilationResult]:
        """Compile sources."""
        console.print("[yellow bold]Compilation started[/]")
        res: list[CompilationResult] = []

        # up to min(32, os.cpu_count() + 4) workers
        with concurrent.futures.ProcessPoolExecutor() as executor:
            f2s = {
                executor.submit(self.compile_file, s): s for s in self.sources
            }
            for future in concurrent.futures.as_completed(f2s):
                f_res = future.result()
                res.append(f_res)

                if not f_res.success:
                    raise CompilationError("Build failed.")

        console.print("[green]Compilation finished successfully[/]")
        return res

    @property
    def app_path(self) -> str:
        return os.path.join(self._build_dir, self.app_name)

    def __need_relink(self, obj_paths: list[str]) -> bool:
        if not os.path.exists(self.app_path):
            return True
        app_mtime = os.path.getmtime(self.app_path)
        return any(os.path.getmtime(obj) > app_mtime for obj in obj_paths)

    def link(self, obj_paths: list[str]):
        console.print("[yellow bold]Linking...[/]")
        link_cmd = [
            self.compiler,
            *obj_paths,
            *self.libs,
            "-o",
            self.app_path
        ]
        if not self.__need_relink(obj_paths):
            console.print("[yellow]No changes detected. Skipping link step...[/]")
        else:
            if self._verbose:
                console.print(f"Linking command: {' '.join(link_cmd)}")
            _ = subprocess.run(link_cmd, check=True)
            console.print("[green]Linking finished successfully[/]")

    def build(
            self,
            gen_db: bool = False,
            verbose: bool = False,
            build_type: BuildType = BuildType.Debug,
    ):
        """
        Build executable according to the config.
        If `gen_db` is True, re-generates compile_commands.json
        Returns relative path to the executable.
        """
        self._verbose = verbose
        self.build_type = build_type
        self._build_dir = self._build_dir / Path(self.build_type.value)
        match self.build_type:
            case BuildType.Debug:
                self.cflags.extend(["-O0", "-g", "-D", "DEBUG"])
            case BuildType.Release:
                self.cflags.extend(["-O3", "-D", "NDEBUG"])
        console.print(f"[yellow bold]Build type: {self.build_type}.[/]")
        
        res = self.compile()
        self.link([r.obj_path for r in res])
        console.print("[green bold]\nBuilt executable.[/]")
        if gen_db:
            json.dump([r.cdb_entry for r in res], open("compile_commands.json", "w"), indent=2)
            console.print("[yellow bold]Updated compile_commands.json.[/]")

    def run(self):
        _ = subprocess.run(self.app_path)

    def clean(self):
        if os.path.isdir(self._build_dir):
            shutil.rmtree(self._build_dir)
            console.print("[yellow bold]Cleaning build directory done.[/]")
        else:
            console.print("[yellow bold]Build directory does not exist. Nothing to clean.[/]")
