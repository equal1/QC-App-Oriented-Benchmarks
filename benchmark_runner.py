import importlib
import inspect
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Sequence

from pydantic import BaseModel

### attempt to set up running stuff
from qbraid import QbraidProvider
from qiskit import QuantumCircuit

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

class QBraidBackEnd():
    def __init__(self):
        self.name = "QBraidEqual1Backend"

class QBraidResult:
    def __init__(self, counts, exec_time):
        self.exec_time = exec_time
        self.counts = counts
    def get_counts(self, qc):
        return self.counts

class QBraidExecutor():
    def __init__(self):
        provider = QbraidProvider()
        self.device = provider.get_device("equal1_simulator_cpu")

    def __call__(self, qc : QuantumCircuit, backend_name : str, backend, shots, **kwargs) -> QBraidResult:
        print(f"attempting to run {qc} on {backend_name}, on {backend} with {shots} and {kwargs}")

        job = self.device.run(qc, shots=shots, noise_model="bell1-6-lin")
        job.wait_for_final_state()  # Wait for the job to complete and get final state

        if job.status().name != "COMPLETED":
            # raise ValueError("job failed")
            assert f"\n@@@@@@@@@@@@@@ \n JOB FAILED for {qc} \n @@@@@@@@@@@@@@@@@@ \n "

        result = job.result()
        counts = result.data.get_counts()
        print(counts)

        result_json = job.client.get_job_results(job.id)
        inner_exec_time = result_json["inner_execution_time"]

        return QBraidResult(counts, inner_exec_time)


common_params : dict[str, Any] = {
    "backend_id" : "qasm_simulator",
    "provider_backend" : QBraidBackEnd(),
    "hub" : "",
    "group" : "",
    "project" : "",
    "exec_options" : {
        "executor" : QBraidExecutor()
    },
    "context" : None,
}

# default_params : dict[str, Any] = {
#     "backend_id" : "qasm_simulator",
#     "provider_backend" : None,
#     "hub" : "",
#     "group" : "",
#     "project" : "",
#     "exec_options" : {},
#     "context" : None,
# }

class ConfiguredParams(BaseModel):
    min_qubits : int = 2
    max_qubits : int = 6
    skip_qubits : int = 1
    max_circuits : int = 6
    num_shots : int = 1000



for benchmark_name, module_name in benchmark_paths.items():
    path: Path = Path(benchmark_name)
    path = path / "qiskit" if benchmark_name not in has_generic_form else path
    assert path.is_dir(), f"Computed path {str(path)} is not a valid directory"
    with temporarily_on_syspaths([path]):
        with load_benchmark_module(module_name) as module:
            if hasattr(module, "run"):
                config = ConfiguredParams()
                params = { **config.model_dump(), **common_params}
                if benchmark_name in has_generic_form:
                    params["api"] = "qiskit"

                module.run(**params)

import sys
import metrics

sys.path.insert(1, "_common")

metrics.plot_all_app_metrics("qasm_simulator", do_all_plots=False, include_apps=None)
