import importlib
import inspect
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Sequence

from pydantic import BaseModel

benchmark_paths: dict[str, str] = {
    # Tutorial
    "deutsch-jozsa": "dj_benchmark",
    "bernstein-vazirani": "bv_benchmark",
    "hidden-shift": "hs_benchmark",

    # Subroutine
    "phase-estimation": "pe_benchmark",
    "amplitude-estimation": "ae_benchmark",

    # Functional
    "hhl": "hhl_benchmark",
    "grovers": "grovers_benchmark",
    "hamiltonian-simulation": "hamiltonian_simulation_benchmark",
    "monte-carlo": "mc_benchmark",
    "vqe": "vqe_benchmark",
    "shors": "shors_benchmark",

    # For magic reasons this has to be the last one , so we
    # can at least force a reload on this module

    "quantum-fourier-transform": "qft_benchmark",

}

has_generic_form: list[str] = [
    "bernstein-vazirani",
    "hidden-shift",
    "quantum-fourier-transform",
    "phase-estimation",
]

methods: dict[str, int] = {
    "bernstein-vazirani": 2,
    "hamiltonian-simulation": 2,
    "quantum-fourier-transform": 2,
    "vqe": 2,
    "shors": 2,
}


@contextmanager
def temporarily_on_syspaths(paths: Sequence[Path]):
    """Add *path* to the *front* of sys.path while inside the with-block."""
    saved_sys_paths = sys.path.copy()

    for path in paths:
        sys.path.append(str(path))
    try:
        yield
    finally:
        sys.path = saved_sys_paths

@contextmanager
def load_benchmark_module(module_name : str):
    existing_module = sys.modules.get(module_name, None)
    if existing_module is not None:
        temporary_module = importlib.reload(existing_module)
    else:
        temporary_module = importlib.import_module(module_name)

    try:
        yield temporary_module
    finally:
        del temporary_module


general_annotations : dict[str, list[str]] = {}

for benchmark_name, module_name in benchmark_paths.items():
    path: Path = Path(benchmark_name)
    path = path / "qiskit" if benchmark_name not in has_generic_form else path
    assert path.is_dir(), f"Computed path {str(path)} is not a valid directory"
    with temporarily_on_syspaths([path]):
        with load_benchmark_module(module_name) as module:
            if hasattr(module, "run"):
                annot = inspect.signature(module.run)
                general_annotations[benchmark_name] = list(annot.parameters.keys())


parameters_in_benches : dict[str, list[str]] = {}
for bench, params in general_annotations.items():
    max_tab = max( len(s) for s in general_annotations)
    tab_count = max_tab - len(bench)
    spaces = " " * tab_count
    print(f"{bench} : {spaces} {params}")

    for param in params:
        parameters_in_benches.setdefault(param, []).append(bench)
print("\n####\n")
for param, bech in parameters_in_benches.items():
    max_tab = max( len(s) for s in parameters_in_benches)
    tab_count = max_tab - len(param)
    spaces = " " * tab_count
    print(f"{param}: {spaces} {sorted(bech)}")
