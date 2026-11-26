"""Tests for MagicState-Lab. Every test grades a computed number
against a closed form or an independent implementation in main.py."""
import math
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import main as ms

TOL = 1e-9


def test_pauli_expectations_zero_state():
    states, _ = ms.named_states()
    exps = ms.pauli_expectations(ms.ket_to_rho(states["zero"]), 1)
    assert abs(exps["I"] - 1.0) < 1e-12 and abs(exps["Z"] - 1.0) < 1e-12
    assert abs(exps["X"]) < 1e-12 and abs(exps["Y"]) < 1e-12


def test_density_matrices_valid():
    states, states2 = ms.named_states()
    for psi in list(states.values()) + list(states2.values()):
        rho = ms.ket_to_rho(psi)
        assert abs(ms.trace(rho) - 1.0) < 1e-12
        assert ms.mat_max_dev(rho, ms.dagger(rho)) < 1e-12


def test_cnot_truth_table():
    cnot = ms.cnot_matrix(0, 1)
    basis = [[1 + 0j, 0j, 0j, 0j], [0j, 1 + 0j, 0j, 0j],
             [0j, 0j, 1 + 0j, 0j], [0j, 0j, 0j, 1 + 0j]]
    expect = [basis[0], basis[1], basis[3], basis[2]]
    for b, e in zip(basis, expect):
        out = ms.matvec(cnot, b)
        assert max(abs(x - y) for x, y in zip(out, e)) < 1e-12


def test_partial_trace_and_measurement():
    states, _ = ms.named_states()
    prod = ms.kron(ms.ket_to_rho(states["T"]),
                   ms.ket_to_rho(states["plus"]))
    assert ms.mat_max_dev(ms.partial_trace(prod, keep=0),
                          ms.ket_to_rho(states["T"])) < 1e-12
    assert ms.mat_max_dev(ms.partial_trace(prod, keep=1),
                          ms.ket_to_rho(states["plus"])) < 1e-12
    branches = ms.measure_qubit(ms.kron(ms.ket_to_rho(states["plus"]),
                                        ms.ket_to_rho(states["plus"])), 1)
    assert all(abs(p - 0.5) < 1e-12 for _, p, _ in branches)


def test_m2_stabilizer_states_zero():
    states, states2 = ms.named_states()
    for name in ("zero", "one", "plus", "plus_i"):
        assert abs(ms.stabilizer_renyi_2(
            ms.ket_to_rho(states[name]), 1)) < TOL
    assert abs(ms.stabilizer_renyi_2(
        ms.ket_to_rho(states2["bell"]), 2)) < TOL
    assert abs(ms.stabilizer_renyi_2(
        ms.ket_to_rho(states2["plus_plus"]), 2)) < TOL


def test_m2_t_state_closed_form():
    states, _ = ms.named_states()
    m2 = ms.stabilizer_renyi_2(ms.ket_to_rho(states["T"]), 1)
    assert abs(m2 - (-math.log2(3.0 / 4.0))) < 1e-12
    assert abs(m2 - 0.4150374992788438) < 1e-12


def test_m2_h_type_and_body_diagonal():
    states, _ = ms.named_states()
    assert abs(ms.stabilizer_renyi_2(ms.ket_to_rho(states["H_type"]), 1)
               - ms.M2_T_ANALYTIC) < 1e-12
    assert abs(ms.stabilizer_renyi_2(
        ms.ket_to_rho(states["body_diagonal"]), 1)
        - math.log2(3.0 / 2.0)) < 1e-12


def test_m2_additivity():
    _, states2 = ms.named_states()
    assert abs(ms.stabilizer_renyi_2(ms.ket_to_rho(states2["T_zero"]), 2)
               - ms.M2_T_ANALYTIC) < 1e-12
    assert abs(ms.stabilizer_renyi_2(ms.ket_to_rho(states2["T_T"]), 2)
               - 2.0 * ms.M2_T_ANALYTIC) < 1e-12


def test_m2_matches_bloch_referee():
    for theta_deg in (20.0, 55.0, 90.0, 130.0, 170.0):
        for phi_deg in (0.0, 40.0, 90.0, 200.0):
            psi = ms.tilted_ket(math.radians(theta_deg),
                                math.radians(phi_deg))
            assert abs(ms.stabilizer_renyi_2(ms.ket_to_rho(psi), 1)
                       - ms.bloch_m2_referee(psi)) < 1e-12


def test_distill_map_values():
    assert abs(ms.distill_step(0.10) - 0.035) < 1e-15
    assert abs(ms.distill_step(0.05) - 0.004375) < 1e-15
    assert abs(ms.distill_step(0.01) / 0.01 - 0.0035) < 1e-12


def test_threshold_matches_analytic():
    p_star = ms.locate_threshold()
    assert abs(p_star - 1.0 / math.sqrt(35.0)) < TOL
    assert abs(p_star - 0.1690308509457033) < TOL
    assert abs(ms.distill_step(p_star) - p_star) < TOL


def test_below_threshold_shrinks_above_grows():
    below = ms.distill_iterate(0.10, 5)
    assert all(below[i + 1] < below[i] for i in range(len(below) - 1))
    assert below[3] < 1e-6 and below[5] < 1e-18
    above = ms.distill_iterate(0.25, 2)
    assert above[1] > 0.25 and above[2] > above[1]


def test_distill_resources():
    res = ms.distill_rounds_to_target(0.10, 1e-6)
    assert res["rounds"] == 3 and res["raw_states"] == 3375
    res = ms.distill_rounds_to_target(0.10, 1e-12)
    assert res["rounds"] == 4 and res["raw_states"] == 50625


def test_inject_perfect():
    states, _ = ms.named_states()
    rho_out, probs = ms.inject_t(ms.ket_to_rho(states["plus"]),
                                 ms.t_state_rho())
    assert ms.mat_max_dev(rho_out, ms.t_state_rho()) < 1e-12
    assert abs(probs[0] - 0.5) < 1e-12 and abs(probs[1] - 0.5) < 1e-12


def test_inject_error_transfer_exact():
    for row in ms.inject_report()["rows"]:
        assert abs(row["depolarizing"]["epsilon_out"]
                   - row["p"] / 2.0) < 1e-12
        assert abs(row["phase_flip"]["epsilon_out"] - row["p"]) < 1e-12
        assert abs((1.0 - row["depolarizing"]["magic_fidelity"])
                   - row["p"] / 2.0) < 1e-12
        assert abs((1.0 - row["phase_flip"]["magic_fidelity"])
                   - row["p"]) < 1e-12
        if row["p"] > 0:
            assert row["depolarizing"]["epsilon_out"] < row["p"]


def test_classifier_scenarios():
    rep = ms.classifier_report()
    assert rep["t_state_p_0.001"] == "inject-ready"
    assert rep["t_state_p_0.05"] == "distill-first"
    assert rep["t_state_p_0.25"] == "above-threshold"
    assert rep["plus_state_p_0.05"] == "no-magic"
    assert rep["body_diagonal_p_0.08"] == "distill-first"


def test_classifier_matches_policy_on_grid():
    for features, _ in ms.TRAINING_GRID:
        assert ms.classify_supply(*features) == ms.policy_label(*features)


def test_hold_gates():
    assert len(ms.HOLD_GATES) == 14
    assert ms.gate("fault_tolerant_computer_claim") == "HOLD"
    assert ms.gate("real_hardware_distillation_claim") == "HOLD"
    assert ms.gate("run_simulation") == "PROCEED"


def test_seats_cannot_override():
    brains = ms.brains_report()
    assert brains["decider"]["can_override_hold"] is False
    assert brains["advisor"]["can_override_hold"] is False
    assert brains["flow"]["rendered"] is False
    assert brains["flow"]["live"] == 0


def test_run_checks_all_pass():
    checks = ms.run_checks()
    assert all(ok for _, ok in checks), [n for n, ok in checks if not ok]


def test_hold_demo_exits_2():
    root = Path(__file__).resolve().parent.parent
    proc = subprocess.run([sys.executable, str(root / "main.py"), "hold-demo"],
                          capture_output=True, text=True)
    assert proc.returncode == 2
    assert "HOLD" in proc.stdout


def test_demo_deterministic():
    root = Path(__file__).resolve().parent.parent
    a = subprocess.run([sys.executable, str(root / "main.py"), "demo"],
                       capture_output=True, text=True)
    b = subprocess.run([sys.executable, str(root / "main.py"), "demo"],
                       capture_output=True, text=True)
    assert a.returncode == 0 and b.returncode == 0
    assert a.stdout == b.stdout
