#!/usr/bin/env python3
"""
QED-C Application-Oriented Benchmarks - Modularized with qBraid Execution

This script runs all supported benchmarks using the modularized approach with
qBraid/Equal1 execution backend.

Key Features:
- Modularized problem generation using get_circuits=True
- Execution via qBraid API with Equal1 backend
- Configurable global parameters for all benchmarks
- Automatic metrics collection and visualization
"""

import base64
import json
import os
from typing import Dict, List, Tuple

from qbraid import QbraidProvider
from qiskit import QuantumCircuit, qasm2, qasm3

from _common import metrics
from _common.qiskit import execute as ex


# ============================================================================
# GLOBAL CONFIGURATION
# ============================================================================

# Benchmark execution parameters
MIN_QUBITS = 6
MAX_QUBITS = 6
SKIP_QUBITS = 1
MAX_CIRCUITS = 1
NUM_SHOTS = 1000

# qBraid/Equal1 device configuration
EQUAL1_DEVICE = "equal1_simulator"
EQUAL1_NOISE_MODEL = "bell2-17-gen-preview"
SIMULATION_BACKEND = "DensityMatrix"  # Options: "DensityMatrix", "StateVector", etc.
SIMULATION_PLATFORM = "CPU"  # Options: "CPU", "GPU"
OPTIMIZATION_LEVEL = 2

# Benchmark specific overrides
VQE_NUM_SHOTS = NUM_SHOTS

# Backend configuration for benchmarks
BACKEND_ID = "qasm_simulator"


metrics.show_plot_images = False

# ============================================================================
# QBRAID EXECUTOR CLASSES
# ============================================================================


class QBraidBackEnd:
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


class QBraidExecutor:
    def __init__(self, device_name, noise_model, backend, platform, opt_level):
        provider = QbraidProvider()
        self.device = provider.get_device(device_name)
        self.noise_model = noise_model
        self.backend = backend
        self.platform = platform
        self.opt_level = opt_level

    def __call__(
        self, qc: QuantumCircuit, backend_name: str, backend, shots, **kwargs
    ) -> QBraidResult:
        print(
            f"Running circuit on {backend_name} ({self.backend}/{self.platform}) with {shots} shots"
        )

        runtime_options = {
            "simulation_platform": self.platform,
            "execution_options": {"optimization_level": self.opt_level},
        }

        job = self.device.run(
            qc,
            shots=shots,
            noise_model=self.noise_model,
            runtime_options=runtime_options,
            backend=self.backend,
        )
        job.wait_for_final_state()

        if job.status().name != "COMPLETED":
            job_result = job.client.get_job_results(job.id)
            error_msg = job_result["statusText"]
            print(f"\n{'=' * 80}\nJOB FAILED\nError: {error_msg}\n{'=' * 80}\n")
            raise RuntimeError(f"Job failed: {error_msg}")

        result = job.result()
        counts = result.data.get_counts()

        result_json = job.client.get_job_results(job.id)
        inner_exec_time = result_json["executionMetrics"]["executor"]

        transpiled_circuit = base64.b64decode(result_json["compiledOutput"]).decode(
            "utf-8"
        )
        try:
            transpiled_qc = qasm2.loads(
                transpiled_circuit, custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS
            )
        except qasm2.exceptions.QASM2ParseError:
            try:
                transpiled_qc = qasm3.loads(transpiled_circuit)
            except qasm3.exceptions.QASM3Error as e:
                print(f"Warning: Could not parse transpiled circuit: {e}")
                transpiled_qc = None

        from _common.qiskit.execute import get_circuit_metrics

        circuit_metrics = get_circuit_metrics(transpiled_qc) if transpiled_qc else {}

        return QBraidResult(counts, inner_exec_time, circuit_metrics)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def prepare_circuits_and_metrics(circuits: Dict, metadata: Dict) -> Tuple[List, List]:
    """
    Convert circuits dictionary to flat list and prepare metrics.

    Args:
        circuits: Dictionary of circuits organized by qubit count
        metadata: Metadata from circuit generation

    Returns:
        tuple: (circuit_identifiers, flat_circuits)
    """
    metadata.pop("subtitle", None)
    metrics.circuit_metrics = metadata.copy()

    circuit_identifiers = []
    flat_circuits = []

    for num_qubits in circuits.keys():
        for circuit_id in circuits[num_qubits].keys():
            circuit_identifiers.append((num_qubits, circuit_id))
            flat_circuits.append(circuits[num_qubits][circuit_id])

            ex.compute_and_store_circuit_info(
                circuits[num_qubits][circuit_id],
                str(num_qubits),
                str(circuit_id),
                do_transpile_metrics=True,
                use_normalized_depth=True,
            )

    return circuit_identifiers, flat_circuits


def execute_circuits(flat_circuits: List, shots: int) -> List[QBraidResult]:
    """
    Execute circuits using qBraid executor.

    Args:
        flat_circuits: List of quantum circuits to execute
        shots: Number of shots for each circuit

    Returns:
        list: Results for each circuit
    """
    results = []
    for idx, qc in enumerate(flat_circuits):
        print(f"  Executing circuit {idx + 1}/{len(flat_circuits)}...")
        result = executor(qc, BACKEND_ID, None, shots)
        results.append(result)
    return results


def analyze_and_plot(
    benchmark_name: str,
    circuit_identifiers: List[Tuple],
    results: List[QBraidResult],
    analyze_func,
    num_shots: int,
    **analyze_kwargs,
):
    """
    Analyze results and create plots.

    Args:
        benchmark_name: Name of the benchmark for plot titles
        circuit_identifiers: List of (num_qubits, circuit_id) tuples
        results: List of execution results
        analyze_func: Function to analyze results (from benchmark module)
        num_shots: Number of shots used
        **analyze_kwargs: Additional kwargs for analyze function
    """
    for idx, (num_qubits, circuit_id) in enumerate(circuit_identifiers):
        counts = results[idx].get_counts(None)
        _, fidelity = analyze_func(
            None, results[idx], int(num_qubits), num_shots, **analyze_kwargs
        )
        metrics.store_metric(num_qubits, circuit_id, "fidelity", fidelity)

    metrics.aggregate_metrics()
    subtitle = f"Benchmark Results - {benchmark_name}"
    metrics.circuit_metrics["subtitle"] = (
        f"device = {EQUAL1_DEVICE} ({SIMULATION_BACKEND}/{SIMULATION_PLATFORM})"
    )

    filters = ["fidelity", "hf_fidelity", "depth", "2q", "vbplot"]
    metrics.plot_metrics(subtitle, filters=filters)


# ============================================================================
# BENCHMARK RUNNERS
# ============================================================================


def run_deutsch_jozsa():
    """Run Deutsch-Jozsa Benchmark"""
    print("=" * 80)
    print("Running Deutsch-Jozsa Benchmark")
    print("=" * 80)

    from deutsch_jozsa import dj_benchmark

    circuits, metadata = dj_benchmark.run(
        min_qubits=MIN_QUBITS,
        max_qubits=MAX_QUBITS,
        skip_qubits=SKIP_QUBITS,
        max_circuits=MAX_CIRCUITS,
        num_shots=NUM_SHOTS,
        get_circuits=True,
    )

    circuit_identifiers, flat_circuits = prepare_circuits_and_metrics(
        circuits, metadata
    )
    print(f"Generated {len(flat_circuits)} circuits")

    results = execute_circuits(flat_circuits, NUM_SHOTS)

    # Analyze results
    for idx, (num_qubits, circuit_id) in enumerate(circuit_identifiers):
        counts = results[idx].get_counts(None)
        _, fidelity = dj_benchmark.analyze_and_print_result(
            None, results[idx], int(num_qubits), NUM_SHOTS
        )
        metrics.store_metric(num_qubits, circuit_id, "fidelity", fidelity)

    # Plot results
    metrics.aggregate_metrics()
    subtitle = "Benchmark Results - Deutsch-Jozsa - Qiskit"
    metrics.circuit_metrics["subtitle"] = (
        f"device = {EQUAL1_DEVICE} ({SIMULATION_BACKEND}/{SIMULATION_PLATFORM})"
    )
    metrics.plot_metrics(
        subtitle, filters=["fidelity", "hf_fidelity", "depth", "2q", "vbplot"]
    )

    print("✓ Deutsch-Jozsa completed\n")


def run_bernstein_vazirani():
    """Run Bernstein-Vazirani (Method 1) Benchmark"""
    print("=" * 80)
    print("Running Bernstein-Vazirani (Method 1) Benchmark")
    print("=" * 80)

    from bernstein_vazirani import bv_benchmark

    circuits, metadata = bv_benchmark.run(
        min_qubits=MIN_QUBITS,
        max_qubits=MAX_QUBITS,
        skip_qubits=SKIP_QUBITS,
        max_circuits=MAX_CIRCUITS,
        num_shots=NUM_SHOTS,
        method=1,
        get_circuits=True,
    )

    circuit_identifiers, flat_circuits = prepare_circuits_and_metrics(
        circuits, metadata
    )
    print(f"Generated {len(flat_circuits)} circuits")

    results = execute_circuits(flat_circuits, NUM_SHOTS)

    for idx, (num_qubits, circuit_id) in enumerate(circuit_identifiers):
        counts = results[idx].get_counts(None)
        _, fidelity = bv_benchmark.analyze_and_print_result(
            None, results[idx], int(num_qubits), NUM_SHOTS, s_int=int(circuit_id)
        )
        metrics.store_metric(num_qubits, circuit_id, "fidelity", fidelity)

    metrics.aggregate_metrics()
    subtitle = "Benchmark Results - Bernstein-Vazirani (Method 1) - Qiskit"
    metrics.circuit_metrics["subtitle"] = (
        f"device = {EQUAL1_DEVICE} ({SIMULATION_BACKEND}/{SIMULATION_PLATFORM})"
    )
    metrics.plot_metrics(
        subtitle, filters=["fidelity", "hf_fidelity", "depth", "2q", "vbplot"]
    )

    print("✓ Bernstein-Vazirani completed\n")


def run_hidden_shift():
    """Run Hidden Shift Benchmark"""
    print("=" * 80)
    print("Running Hidden Shift Benchmark")
    print("=" * 80)

    from hidden_shift import hs_benchmark

    circuits, metadata = hs_benchmark.run(
        min_qubits=MIN_QUBITS,
        max_qubits=MAX_QUBITS,
        max_circuits=MAX_CIRCUITS,
        num_shots=NUM_SHOTS,
        get_circuits=True,
    )

    circuit_identifiers, flat_circuits = prepare_circuits_and_metrics(
        circuits, metadata
    )
    print(f"Generated {len(flat_circuits)} circuits")

    results = execute_circuits(flat_circuits, NUM_SHOTS)

    # Analyze results
    for idx, (num_qubits, circuit_id) in enumerate(circuit_identifiers):
        counts = results[idx].get_counts(None)
        _, fidelity = hs_benchmark.analyze_and_print_result(
            None, results[idx], int(num_qubits), NUM_SHOTS, s_int=int(circuit_id)
        )
        metrics.store_metric(num_qubits, circuit_id, "fidelity", fidelity)

    # Plot results
    metrics.aggregate_metrics()
    subtitle = "Benchmark Results - Hidden Shift - Qiskit"
    metrics.circuit_metrics["subtitle"] = (
        f"device = {EQUAL1_DEVICE} ({SIMULATION_BACKEND}/{SIMULATION_PLATFORM})"
    )
    metrics.plot_metrics(
        subtitle, filters=["fidelity", "hf_fidelity", "depth", "2q", "vbplot"]
    )

    print("✓ Hidden Shift completed\n")


def run_qft_method1():
    """Run Quantum Fourier Transform (Method 1) Benchmark"""
    print("=" * 80)
    print("Running Quantum Fourier Transform (Method 1) Benchmark")
    print("=" * 80)

    from quantum_fourier_transform import qft_benchmark

    circuits, metadata = qft_benchmark.run(
        min_qubits=MIN_QUBITS,
        max_qubits=MAX_QUBITS,
        skip_qubits=SKIP_QUBITS,
        max_circuits=MAX_CIRCUITS,
        num_shots=NUM_SHOTS,
        method=1,
        get_circuits=True,
    )

    circuit_identifiers, flat_circuits = prepare_circuits_and_metrics(
        circuits, metadata
    )
    print(f"Generated {len(flat_circuits)} circuits")

    results = execute_circuits(flat_circuits, NUM_SHOTS)

    # Analyze results
    for idx, (num_qubits, circuit_id) in enumerate(circuit_identifiers):
        counts = results[idx].get_counts(None)
        _, fidelity = qft_benchmark.analyze_and_print_result(
            None,
            results[idx],
            int(num_qubits),
            NUM_SHOTS,
            s_int=int(circuit_id),
            method=1,
        )
        metrics.store_metric(num_qubits, circuit_id, "fidelity", fidelity)

    # Plot results
    metrics.aggregate_metrics()
    subtitle = "Benchmark Results - Quantum Fourier Transform (Method 1) - Qiskit"
    metrics.circuit_metrics["subtitle"] = (
        f"device = {EQUAL1_DEVICE} ({SIMULATION_BACKEND}/{SIMULATION_PLATFORM})"
    )
    metrics.plot_metrics(
        subtitle, filters=["fidelity", "hf_fidelity", "depth", "2q", "vbplot"]
    )

    print("✓ QFT Method 1 completed\n")


def run_qft_method2():
    """Run Quantum Fourier Transform (Method 2) Benchmark"""
    print("=" * 80)
    print("Running Quantum Fourier Transform (Method 2) Benchmark")
    print("=" * 80)

    from quantum_fourier_transform import qft_benchmark

    circuits, metadata = qft_benchmark.run(
        min_qubits=MIN_QUBITS,
        max_qubits=MAX_QUBITS,
        skip_qubits=SKIP_QUBITS,
        max_circuits=MAX_CIRCUITS,
        num_shots=NUM_SHOTS,
        method=2,
        get_circuits=True,
    )

    circuit_identifiers, flat_circuits = prepare_circuits_and_metrics(
        circuits, metadata
    )
    print(f"Generated {len(flat_circuits)} circuits")

    results = execute_circuits(flat_circuits, NUM_SHOTS)

    # Analyze results
    for idx, (num_qubits, circuit_id) in enumerate(circuit_identifiers):
        counts = results[idx].get_counts(None)
        _, fidelity = qft_benchmark.analyze_and_print_result(
            None,
            results[idx],
            int(num_qubits),
            NUM_SHOTS,
            s_int=int(circuit_id),
            method=2,
        )
        metrics.store_metric(num_qubits, circuit_id, "fidelity", fidelity)

    # Plot results
    metrics.aggregate_metrics()
    subtitle = "Benchmark Results - Quantum Fourier Transform (Method 2) - Qiskit"
    metrics.circuit_metrics["subtitle"] = (
        f"device = {EQUAL1_DEVICE} ({SIMULATION_BACKEND}/{SIMULATION_PLATFORM})"
    )
    metrics.plot_metrics(
        subtitle, filters=["fidelity", "hf_fidelity", "depth", "2q", "vbplot"]
    )

    print("✓ QFT Method 2 completed\n")


def run_grovers():
    """Run Grover's Search Benchmark"""
    print("=" * 80)
    print("Running Grover's Search Benchmark")
    print("=" * 80)

    from grovers import grovers_benchmark

    circuits, metadata = grovers_benchmark.run(
        min_qubits=MIN_QUBITS,
        max_qubits=MAX_QUBITS,
        skip_qubits=SKIP_QUBITS,
        max_circuits=MAX_CIRCUITS,
        num_shots=NUM_SHOTS,
        get_circuits=True,
    )

    circuit_identifiers, flat_circuits = prepare_circuits_and_metrics(
        circuits, metadata
    )
    print(f"Generated {len(flat_circuits)} circuits")

    results = execute_circuits(flat_circuits, NUM_SHOTS)

    # Analyze results
    for idx, (num_qubits, circuit_id) in enumerate(circuit_identifiers):
        counts = results[idx].get_counts(None)
        _, fidelity = grovers_benchmark.analyze_and_print_result(
            None, results[idx], int(num_qubits), NUM_SHOTS, marked_item=int(circuit_id)
        )
        metrics.store_metric(num_qubits, circuit_id, "fidelity", fidelity)

    # Plot results
    metrics.aggregate_metrics()
    subtitle = "Benchmark Results - Grover's Search - Qiskit"
    metrics.circuit_metrics["subtitle"] = (
        f"device = {EQUAL1_DEVICE} ({SIMULATION_BACKEND}/{SIMULATION_PLATFORM})"
    )
    metrics.plot_metrics(
        subtitle, filters=["fidelity", "hf_fidelity", "depth", "2q", "vbplot"]
    )

    print("✓ Grover's Search completed\n")


def run_phase_estimation():
    """Run Phase Estimation Benchmark"""
    print("=" * 80)
    print("Running Phase Estimation Benchmark")
    print("=" * 80)

    from phase_estimation import pe_benchmark

    circuits, metadata = pe_benchmark.run(
        min_qubits=MIN_QUBITS,
        max_qubits=MAX_QUBITS,
        skip_qubits=SKIP_QUBITS,
        max_circuits=MAX_CIRCUITS,
        num_shots=NUM_SHOTS,
        get_circuits=True,
    )

    circuit_identifiers, flat_circuits = prepare_circuits_and_metrics(
        circuits, metadata
    )
    print(f"Generated {len(flat_circuits)} circuits")

    results = execute_circuits(flat_circuits, NUM_SHOTS)

    for idx, (num_qubits, circuit_id) in enumerate(circuit_identifiers):
        counts = results[idx].get_counts(None)
        _, fidelity = pe_benchmark.analyze_and_print_result(
            None, results[idx], int(num_qubits), float(circuit_id), NUM_SHOTS
        )
        metrics.store_metric(num_qubits, circuit_id, "fidelity", fidelity)

    metrics.aggregate_metrics()
    subtitle = "Benchmark Results - Phase Estimation - Qiskit"
    metrics.circuit_metrics["subtitle"] = (
        f"device = {EQUAL1_DEVICE} ({SIMULATION_BACKEND}/{SIMULATION_PLATFORM})"
    )
    metrics.plot_metrics(
        subtitle, filters=["fidelity", "hf_fidelity", "depth", "2q", "vbplot"]
    )

    print("✓ Phase Estimation completed\n")


def run_hhl():
    """Run HHL Linear Solver Benchmark"""
    print("=" * 80)
    print("Running HHL Linear Solver Benchmark")
    print("=" * 80)

    from hhl import hhl_benchmark

    hhl_benchmark.verbose = False

    circuits, metadata = hhl_benchmark.run(
        min_qubits=MIN_QUBITS,
        max_qubits=MAX_QUBITS,
        skip_qubits=SKIP_QUBITS,
        max_circuits=MAX_CIRCUITS,
        num_shots=NUM_SHOTS,
        method=1,
        use_best_widths=True,
        get_circuits=True,
    )

    circuit_identifiers, flat_circuits = prepare_circuits_and_metrics(
        circuits, metadata
    )
    print(f"Generated {len(flat_circuits)} circuits")

    #### benchmark generates megablocks.....
    flat_circuits = [circuit.decompose() for circuit in flat_circuits]

    results = execute_circuits(flat_circuits, NUM_SHOTS)

    # Analyze results
    for idx, (num_qubits, circuit_id) in enumerate(circuit_identifiers):
        counts = results[idx].get_counts(None)
        _, fidelity = hhl_benchmark.analyze_and_print_result(
            None, results[idx], int(num_qubits), NUM_SHOTS
        )
        metrics.store_metric(num_qubits, circuit_id, "fidelity", fidelity)

    # Plot results
    metrics.aggregate_metrics()
    subtitle = "Benchmark Results - HHL Linear Solver - Qiskit"
    metrics.circuit_metrics["subtitle"] = (
        f"device = {EQUAL1_DEVICE} ({SIMULATION_BACKEND}/{SIMULATION_PLATFORM})"
    )
    metrics.plot_metrics(
        subtitle, filters=["fidelity", "hf_fidelity", "depth", "2q", "vbplot"]
    )

    print("✓ HHL completed\n")


def run_amplitude_estimation():
    """Run Amplitude Estimation Benchmark"""
    print("=" * 80)
    print("Running Amplitude Estimation Benchmark")
    print("=" * 80)

    from amplitude_estimation import ae_benchmark

    AE_NUM_STATE_QUBITS = 1
    circuits, metadata = ae_benchmark.run(
        min_qubits=MIN_QUBITS,
        max_qubits=MAX_QUBITS,
        skip_qubits=SKIP_QUBITS,
        max_circuits=MAX_CIRCUITS,
        num_shots=NUM_SHOTS,
        num_state_qubits=AE_NUM_STATE_QUBITS,
        get_circuits=True,
    )

    circuit_identifiers, flat_circuits = prepare_circuits_and_metrics(
        circuits, metadata
    )
    print(f"Generated {len(flat_circuits)} circuits")

    #### benchmark generates megablocks.....
    flat_circuits = [
        circuit.decompose().decompose().decompose() for circuit in flat_circuits
    ]

    results = execute_circuits(flat_circuits, NUM_SHOTS)

    # Analyze results
    for idx, (num_qubits, circuit_id) in enumerate(circuit_identifiers):
        counts = results[idx].get_counts(None)
        _, fidelity = ae_benchmark.analyze_and_print_result(
            None,
            results[idx],
            int(num_qubits),
            NUM_SHOTS,
            s_int=int(circuit_id),
            num_state_qubits=AE_NUM_STATE_QUBITS,
        )
        metrics.store_metric(num_qubits, circuit_id, "fidelity", fidelity)

    # Plot results
    metrics.aggregate_metrics()
    subtitle = "Benchmark Results - Amplitude Estimation - Qiskit"
    metrics.circuit_metrics["subtitle"] = (
        f"device = {EQUAL1_DEVICE} ({SIMULATION_BACKEND}/{SIMULATION_PLATFORM})"
    )
    metrics.plot_metrics(
        subtitle, filters=["fidelity", "hf_fidelity", "depth", "2q", "vbplot"]
    )

    print("✓ Amplitude Estimation completed\n")


def run_monte_carlo():
    """Run Monte Carlo Benchmark"""
    print("=" * 80)
    print("Running Monte Carlo Benchmark")
    print("=" * 80)

    from monte_carlo import mc_benchmark

    MC_METHOD = 2
    MC_NUM_STATE_QUBITS = 1
    MC_EPSILON = 0.05
    MC_DEGREE = 2
    circuits, metadata = mc_benchmark.run(
        min_qubits=MIN_QUBITS,
        max_qubits=MAX_QUBITS,
        skip_qubits=SKIP_QUBITS,
        max_circuits=MAX_CIRCUITS,
        num_shots=NUM_SHOTS,
        get_circuits=True,
        method=MC_METHOD,
        num_state_qubits=MC_NUM_STATE_QUBITS,
        epsilon=MC_EPSILON,
        degree=MC_DEGREE,
    )

    circuit_identifiers, flat_circuits = prepare_circuits_and_metrics(
        circuits, metadata
    )
    print(f"Generated {len(flat_circuits)} circuits")

    #### benchmark generates megablocks.....
    flat_circuits = [
        circuit.decompose().decompose().decompose().decompose()
        for circuit in flat_circuits
    ]

    results = execute_circuits(flat_circuits, NUM_SHOTS)


    c_star = (2*MC_EPSILON)**(1/(MC_DEGREE+1))

    # Analyze results
    for idx, (num_qubits, circuit_id) in enumerate(circuit_identifiers):
        counts = results[idx].get_counts(None)
        _, fidelity = mc_benchmark.analyze_and_print_result(
            None,
            results[idx],
            int(num_qubits),
            num_shots=NUM_SHOTS,
            mu=float(circuit_id),
            num_state_qubits=MC_NUM_STATE_QUBITS,
            method=MC_METHOD,
            c_star=c_star,
        )
        metrics.store_metric(num_qubits, circuit_id, "fidelity", fidelity)

    # Plot results
    metrics.aggregate_metrics()
    subtitle = "Benchmark Results - Monte Carlo - Qiskit"
    metrics.circuit_metrics["subtitle"] = (
        f"device = {EQUAL1_DEVICE} ({SIMULATION_BACKEND}/{SIMULATION_PLATFORM})"
    )
    metrics.plot_metrics(
        subtitle, filters=["fidelity", "hf_fidelity", "depth", "2q", "vbplot"]
    )

    print("✓ Monte Carlo completed\n")


def run_hamiltonian_simulation():
    """Run Hamiltonian Simulation (Method 1) Benchmark"""
    print("=" * 80)
    print("Running Hamiltonian Simulation (Method 1) Benchmark")
    print("=" * 80)

    from hamiltonian_simulation import hamiltonian_simulation_benchmark

    circuits, metadata = hamiltonian_simulation_benchmark.run(
        min_qubits=MIN_QUBITS,
        max_qubits=MAX_QUBITS,
        skip_qubits=SKIP_QUBITS,
        max_circuits=MAX_CIRCUITS,
        num_shots=NUM_SHOTS,
        method=1,
        get_circuits=True,
    )

    circuit_identifiers, flat_circuits = prepare_circuits_and_metrics(
        circuits, metadata
    )
    print(f"Generated {len(flat_circuits)} circuits")

    results = execute_circuits(flat_circuits, NUM_SHOTS)

    # Analyze results
    for idx, (num_qubits, circuit_id) in enumerate(circuit_identifiers):
        counts = results[idx].get_counts(None)
        _, fidelity = hamiltonian_simulation_benchmark.analyze_and_print_result(
            None, results[idx], int(num_qubits), NUM_SHOTS
        )
        metrics.store_metric(num_qubits, circuit_id, "fidelity", fidelity)

    # Plot results
    metrics.aggregate_metrics()
    subtitle = "Benchmark Results - Hamiltonian Simulation (Method 1) - Qiskit"
    metrics.circuit_metrics["subtitle"] = (
        f"device = {EQUAL1_DEVICE} ({SIMULATION_BACKEND}/{SIMULATION_PLATFORM})"
    )
    metrics.plot_metrics(
        subtitle, filters=["fidelity", "hf_fidelity", "depth", "2q", "vbplot"]
    )

    print("✓ Hamiltonian Simulation completed\n")


def run_vqe():
    """Run VQE (Method 1) Benchmark"""
    print("=" * 80)
    print("Running VQE (Method 1) Benchmark")
    print("=" * 80)

    from vqe import vqe_benchmark

    circuits, metadata = vqe_benchmark.run(
        min_qubits=MIN_QUBITS,
        max_qubits=MAX_QUBITS,
        max_circuits=MAX_CIRCUITS,
        num_shots=VQE_NUM_SHOTS,
        method=1,
        get_circuits=True,
    )

    circuit_identifiers, flat_circuits = prepare_circuits_and_metrics(
        circuits, metadata
    )
    print(f"Generated {len(flat_circuits)} circuits")

    #### benchmark generates megablocks.....
    flat_circuits = [
        circuit.decompose()
        for circuit in flat_circuits
    ]

    results = execute_circuits(flat_circuits, VQE_NUM_SHOTS)

    from vqe.qiskit.vqe_benchmark import analyze_and_print_result
    # Analyze results
    for idx, (num_qubits, circuit_id) in enumerate(circuit_identifiers):

        qc = flat_circuits[idx]
        # load pre-computed data
        if len(qc.name.split()) == 2:
            filename = os.path.join(os.path.dirname(__file__),
                    f'vqe/_common/precalculated_data_{num_qubits}_qubit.json')
            with open(filename) as f:
                references = json.load(f)
        else:
            filename = os.path.join(os.path.dirname(__file__),
                    f'vqe/_common/precalculated_data_{num_qubits}_qubit_method2.json')
            with open(filename) as f:
                references = json.load(f)

        counts = results[idx].get_counts(None)
        fidelity = analyze_and_print_result(
            qc, results[idx], int(num_qubits), VQE_NUM_SHOTS, references
        )

        if len(qc.name.split()) == 2:
            metrics.store_metric(num_qubits, qc.name.split()[0], 'fidelity', fidelity)
        else:
            metrics.store_metric(num_qubits, qc.name.split()[2], 'fidelity', fidelity)

    # Plot results
    metrics.aggregate_metrics()
    subtitle = "Benchmark Results - VQE (Method 1) - Qiskit"
    metrics.circuit_metrics["subtitle"] = (
        f"device = {EQUAL1_DEVICE} ({SIMULATION_BACKEND}/{SIMULATION_PLATFORM})"
    )
    metrics.plot_metrics(
        subtitle, filters=["fidelity", "hf_fidelity", "depth", "2q", "vbplot"]
    )

    print("✓ VQE completed\n")


def run_shors_method1():
    """Run Shor's Algorithm (Method 1) Benchmark"""
    print("=" * 80)
    print("Running Shor's Algorithm (Method 1) Benchmark")
    print("=" * 80)

    from shors.qiskit import shors_benchmark

    circuits, metadata = shors_benchmark.run(
        min_qubits=MIN_QUBITS,
        max_qubits=MAX_QUBITS,
        max_circuits=1,
        num_shots=NUM_SHOTS,
        method=1,
        get_circuits=True,
    )

    circuit_identifiers, flat_circuits = prepare_circuits_and_metrics(
        circuits, metadata
    )
    print(f"Generated {len(flat_circuits)} circuits")

    results = execute_circuits(flat_circuits, NUM_SHOTS)

    # Analyze results
    for idx, (num_qubits, circuit_id) in enumerate(circuit_identifiers):
        counts = results[idx].get_counts(None)
        _, fidelity = shors_benchmark.analyze_and_print_result(
            None, results[idx], int(num_qubits), NUM_SHOTS
        )
        metrics.store_metric(num_qubits, circuit_id, "fidelity", fidelity)

    # Plot results
    metrics.aggregate_metrics()
    subtitle = "Benchmark Results - Shor's Algorithm (Method 1) - Qiskit"
    metrics.circuit_metrics["subtitle"] = (
        f"device = {EQUAL1_DEVICE} ({SIMULATION_BACKEND}/{SIMULATION_PLATFORM})"
    )
    metrics.plot_metrics(
        subtitle, filters=["fidelity", "hf_fidelity", "depth", "2q", "vbplot"]
    )

    print("✓ Shor's Method 1 completed\n")


def run_shors_method2():
    """Run Shor's Algorithm (Method 2) Benchmark"""
    print("=" * 80)
    print("Running Shor's Algorithm (Method 2) Benchmark")
    print("=" * 80)

    from shors.qiskit import shors_benchmark

    circuits, metadata = shors_benchmark.run(
        min_qubits=MIN_QUBITS,
        max_qubits=MAX_QUBITS,
        max_circuits=1,
        num_shots=NUM_SHOTS,
        method=2,
        get_circuits=True,
    )

    circuit_identifiers, flat_circuits = prepare_circuits_and_metrics(
        circuits, metadata
    )
    print(f"Generated {len(flat_circuits)} circuits")

    results = execute_circuits(flat_circuits, NUM_SHOTS)

    # Analyze results
    for idx, (num_qubits, circuit_id) in enumerate(circuit_identifiers):
        counts = results[idx].get_counts(None)
        _, fidelity = shors_benchmark.analyze_and_print_result(
            None, results[idx], int(num_qubits), NUM_SHOTS
        )
        metrics.store_metric(num_qubits, circuit_id, "fidelity", fidelity)

    # Plot results
    metrics.aggregate_metrics()
    subtitle = "Benchmark Results - Shor's Algorithm (Method 2) - Qiskit"
    metrics.circuit_metrics["subtitle"] = (
        f"device = {EQUAL1_DEVICE} ({SIMULATION_BACKEND}/{SIMULATION_PLATFORM})"
    )
    metrics.plot_metrics(
        subtitle, filters=["fidelity", "hf_fidelity", "depth", "2q", "vbplot"]
    )

    print("✓ Shor's Method 2 completed\n")


# ============================================================================
# MAIN EXECUTION
# ============================================================================


def main():
    """Run all benchmarks"""
    global executor

    print("\n" + "=" * 80)
    print("QED-C Application-Oriented Benchmarks - qBraid Execution")
    print("=" * 80 + "\n")

    # Print configuration
    print("Configuration:")
    print(f"  Qubits: {MIN_QUBITS}-{MAX_QUBITS} (skip={SKIP_QUBITS})")
    print(f"  Circuits per qubit count: {MAX_CIRCUITS}")
    print(f"  Shots: {NUM_SHOTS}")
    print(f"  Device: {EQUAL1_DEVICE}")
    print(f"  Backend: {SIMULATION_BACKEND}")
    print(f"  Platform: {SIMULATION_PLATFORM}")
    print(f"  Noise Model: {EQUAL1_NOISE_MODEL}")
    print(f"  Optimization Level: {OPTIMIZATION_LEVEL}\n")

    # Initialize executor
    executor = QBraidExecutor(
        EQUAL1_DEVICE,
        EQUAL1_NOISE_MODEL,
        SIMULATION_BACKEND,
        SIMULATION_PLATFORM,
        OPTIMIZATION_LEVEL,
    )

    print(f"✓ Executor initialized: {EQUAL1_DEVICE}")
    print(f"  Backend: {SIMULATION_BACKEND}")
    print(f"  Platform: {SIMULATION_PLATFORM}")
    print(f"  Noise Model: {EQUAL1_NOISE_MODEL}\n")

    # Run all benchmarks
    benchmarks = [
        run_deutsch_jozsa,
        run_bernstein_vazirani,
        run_hidden_shift,
        run_qft_method1,
        run_qft_method2,
        run_grovers,
        run_phase_estimation,
        run_hhl,
        run_amplitude_estimation,
        run_monte_carlo,
        # run_hamiltonian_simulation, #broken bench
        run_vqe,
        # run_shors_method1,
        # run_shors_method2,
    ]

    for benchmark_func in benchmarks:
        try:
            benchmark_func()
        except Exception as e:
            print(f"✗ {benchmark_func.__name__} failed with error: {e}\n")
            continue

    # Print combined results
    print("=" * 80)
    print("Combined Benchmark Results")
    print("=" * 80 + "\n")

    metrics.plot_all_app_metrics(BACKEND_ID, do_all_plots=False, include_apps=None)

    print("\n" + "=" * 80)
    print("ALL BENCHMARKS COMPLETED")
    print("=" * 80 + "\n")

    # Close session
    try:
        ex.close_session()
        print("✓ Session closed")
    except Exception as e:
        print(f"Warning: Could not close session: {e}")


if __name__ == "__main__":
    main()
