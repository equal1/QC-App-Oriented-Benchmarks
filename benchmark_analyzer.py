import importlib
import inspect
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Sequence

benchmark_paths: dict[str, str] = {
    # Tutorial
    "deutsch_jozsa": "dj_benchmark",
    "bernstein_vazirani": "bv_benchmark",
    "hidden_shift": "hs_benchmark",

    # Subroutine
    "phase_estimation": "pe_benchmark",
    "amplitude_estimation": "ae_benchmark",

    # Functional
    # "hhl.qiskit": "hhl_benchmark", # Unsupported operation Instruction(name='reset', num_qubits=1, num_clbits=0, params=[]) in circuit
    "grovers": "grovers_benchmark",
    "hamiltonian_simulation": "hamiltonian_simulation_benchmark",
    "monte_carlo": "mc_benchmark",
    "vqe.qiskit": "vqe_benchmark",
    "shors.qiskit": "shors_benchmark",

    # For magic reasons this has to be the last one , so we
    # can at least force a reload on this module

    "quantum_fourier_transform": "qft_benchmark",

}

has_generic_form: list[str] = [
    "bernstein_vazirani",
    "hidden_shift",
    "quantum_fourier_transform",
    "phase_estimation",
]

methods: dict[str, int] = {
    "bernstein-vazirani": 1, # Unsupported operation Instruction(name='reset', num_qubits=1, num_clbits=0, params=[]) in circuit
    "hamiltonian-simulation": 2,
    "quantum-fourier-transform": 2,
    "vqe": 2,
    "shors": 2,
}

@contextmanager
def load_benchmark_module(bench_name : str, module_name : str):
    existing_module = sys.modules.get(module_name, None)
    if existing_module is not None:
        temporary_module = importlib.reload(existing_module)
    else:
        temporary_module = importlib.import_module(bench_name + "." + module_name)

    try:
        yield temporary_module
    finally:
        del temporary_module


general_annotations : dict[str, list[str]] = {}

for benchmark_name, module_name in benchmark_paths.items():
    with load_benchmark_module(benchmark_name, module_name) as module:
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
