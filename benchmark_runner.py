import base64
import importlib
import inspect
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Sequence

from pydantic import BaseModel

### attempt to set up running stuff
from qbraid import QbraidProvider
from qiskit import QuantumCircuit, qasm2, qasm3

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


class QBraidBackEnd():
    def __init__(self):
        self.name = "QBraidEqual1Backend"

class QBraidResult:
    def __init__(self, counts, exec_time, transpiled_circuit_metrics):
        self.exec_time = exec_time
        self.counts = counts
        self.transpiled_circuit_metrics = transpiled_circuit_metrics

    def get_counts(self, qc):
        return self.counts

    def get_transpiled_circuit_metrics(self):
        return self.transpiled_circuit_metrics

class QBraidExecutor():
    def __init__(self):
        provider = QbraidProvider()
        self.device = provider.get_device("equal1_simulator")

    def __call__(self, qc : QuantumCircuit, backend_name : str, backend, shots, **kwargs) -> QBraidResult:
        # print(f"attempting to run {qc} on {backend_name}, on {backend} with {shots} and {kwargs}")

        runtime_options = {
            "simulation_platform": "CPU",
            "execution_options": {"optimization_level": 2},
        }

        backend = "StateVector" if qc.num_qubits > 8 else "DensityMatrix"

        job = self.device.run(qc, shots=shots, noise_model="bell2-17-gen-preview", runtime_options=runtime_options, backend=backend)
        job.wait_for_final_state()  # Wait for the job to complete and get final state

        if job.status().name != "COMPLETED":
            job_result = job.client.get_job_results(job.id)
            print(f"\n@@@@@@@@@@@@@@ \n JOB FAILED for {qc} \n With error message:\n {job_result['statusText']}\n @@@@@@@@@@@@@@@@@@ \n ")


        result = job.result()
        counts = result.data.get_counts()
        # print(counts)

        result_json = job.client.get_job_results(job.id)
        inner_exec_time = result_json['executionMetrics']['executor']


        transpiled_circuit = base64.b64decode(result_json['compiledOutput']).decode('utf-8')
        try:
            transpiled_qc = qasm2.loads(transpiled_circuit, custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS)
        except qasm2.exceptions.QASM2ParseError as e:
            try:
                transpiled_qc = qasm3.loads(transpiled_circuit)
            except qasm3.exceptions.QASM3Error as e:
                print(f"Error parsing transpiled circuit for {qc}: {e}")
                transpiled_qc = None


        from _common.qiskit.execute import get_circuit_metrics
        metrics = get_circuit_metrics(transpiled_qc)


        return QBraidResult(counts, inner_exec_time, metrics)


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

class ConfiguredParams(BaseModel):
    min_qubits : int = 6
    max_qubits : int = 6
    skip_qubits : int = 1
    max_circuits : int = 6
    num_shots : int = 1000
    draw_circuits : bool = False
    plot_results : bool = False


for benchmark_name, module_name in benchmark_paths.items():
    with load_benchmark_module(benchmark_name, module_name) as module:
        if hasattr(module, "run"):
            config = ConfiguredParams()
            params = { **config.model_dump(), **common_params}
            if "qiskit" not in benchmark_name:
                params["api"] = "qiskit"

            module.run(**params)

import sys
import metrics

sys.path.insert(1, "_common")

metrics.plot_all_app_metrics("qasm_simulator", do_all_plots=False, include_apps=None)
