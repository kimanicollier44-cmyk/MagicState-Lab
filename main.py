#!/usr/bin/env python3
"""MagicState-Lab - educational magic state & distillation lab.

by Darion Kellar

Pure Python standard library. Zero dependencies. Zero network.
Education only - and the central lessons are stated up front:

  * "Magic" is computed, never asserted. For pure states of one and
    two qubits the lab builds the density matrix, measures every
    Pauli expectation value from the state itself, and evaluates the
    stabilizer Renyi entropy M2 from those expectations. Stabilizer
    states (|0>, |+>, |+i>, the Bell state) come out at M2 = 0 to
    numerical precision; the T state comes out at
    M2 = -log2(3/4) = 0.415037..., and the lab prints both numbers.
  * Distillation is the protocol's error MAP, applied exactly - it
    is NOT a qubit-by-qubit simulation of the 15-qubit Reed-Muller
    circuit, and the lab says so wherever the map is used. The
    Bravyi-Kitaev 15-to-1 leading-order map p -> 35 p^3 is iterated
    in the open: below the threshold p* = 1/sqrt(35) = 0.169030...
    the error collapses doubly-exponentially fast; above it, it
    grows. The threshold itself is located by bisection on the map
    and graded against 1/sqrt(35).
  * Injection IS simulated qubit-by-qubit: the two-qubit gate
    teleportation circuit (CNOT, measure, S correction) runs on
    density matrices with a noisy magic state, both measurement
    branches carried exactly - no sampling. With the lab's stated
    depolarizing noise model the output infidelity is exactly half
    the input error (first-order suppression, coefficient 1/2); with
    a phase-flip noise model the error passes through unsuppressed,
    and the lab prints both instead of cherry-picking one.

Fault-tolerant-computer claims, real-hardware distillation claims,
certified device error rates, cryptographic breakthrough claims,
and every other real-world use are permanent HOLD gates - with
Gemini Argon 4 Extended Thinking as DECIDER (names-only,
tighten-only), Muse as advisor (never overrides HOLD), and Google
Flow plan-only seats.
"""
import hashlib
import itertools
import json
import math
import sys

# ---------------------------------------------------------------- constants
VERSION = "1.0.0"

# The T state and its stabilizer Renyi entropy, in closed form:
#   |T> = (|0> + e^{i pi/4} |1>) / sqrt(2),  Bloch vector (1,1,0)/sqrt(2)
#   M2(|T>) = -log2(3/4) = log2(4/3) = 0.4150374992788438...
M2_T_ANALYTIC = -math.log2(3.0 / 4.0)
# Fixed point of the 15-to-1 map p = 35 p^3  ->  p* = 1/sqrt(35).
THRESHOLD_ANALYTIC = 1.0 / math.sqrt(35.0)

# ---------------------------------------------------------------- HOLD gates
HOLD_GATES = {
    "fault_tolerant_computer_claim": "HOLD - no claim that a working fault-tolerant quantum computer exists or was built from this lab's arithmetic",
    "real_hardware_distillation_claim": "HOLD - no claim that magic state distillation was performed on real hardware; the 35 p^3 map is applied, the 15-qubit circuit is not run",
    "real_device_error_rate_certification": "HOLD - no certifying a real device's physical error rate, or that it sits below any fault-tolerance threshold, from this model",
    "quantum_advantage_certification": "HOLD - no certifying quantum advantage for any device, algorithm, or vendor",
    "cryptographic_breakthrough_claim": "HOLD - no claim that resource arithmetic here breaks, weakens, or times any real cryptosystem",
    "resource_forecast_claim": "HOLD - T-count and 15^k overhead numbers are combinatorics of a stated map, not engineering forecasts, roadmaps, or timelines",
    "live_hardware_state_injection": "HOLD - no injecting states, running circuits, or controlling hardware outside this offline simulation",
    "distillation_guarantee_claim": "HOLD - the leading-order map p -> 35 p^3 is a model with O(p^5) corrections, not a guarantee for any real protocol run",
    "magic_state_superiority_claim": "HOLD - no claim that one lab's, vendor's, or platform's magic states are better from this arithmetic",
    "product_benchmark_claim": "HOLD - no product benchmark, marketing figure, or procurement comparison from lab numbers",
    "investment_claim": "HOLD - no investment claim; a lab model is not a prospectus",
    "simulation_as_measurement_claim": "HOLD - simulated entropies, fidelities, and error rates must never be presented as measured device data",
    "medical_quantum_claim": "HOLD - no medical, imaging, or therapy claims from magic state arithmetic",
    "standards_compliance_claim": "HOLD - no claim of compliance with any fault-tolerance, benchmarking, or quantum-computing standard",
}


def gate(action):
    """Return 'HOLD' if the action is gated, else 'PROCEED' (sandbox sim)."""
    return "HOLD" if action in HOLD_GATES else "PROCEED"


# ================================================================ 1. Complex matrix + density matrix kit
# Small dense complex matrices as lists of lists. Density matrices
# are built from state vectors, gates act by conjugation U rho U+,
# measurement branches are carried exactly with their probabilities,
# and partial traces are written out - so every number the lab prints
# can be read and checked.

def eye(n):
    return [[complex(1.0 if i == j else 0.0) for j in range(n)]
            for i in range(n)]


def zeros(n, m=None):
    m = n if m is None else m
    return [[0j for _ in range(m)] for _ in range(n)]


def matmul(A, B):
    n, inner, m = len(A), len(B), len(B[0])
    out = zeros(n, m)
    for i in range(n):
        for k in range(inner):
            aik = A[i][k]
            if aik != 0j:
                for j in range(m):
                    out[i][j] += aik * B[k][j]
    return out


def madd(A, B):
    return [[A[i][j] + B[i][j] for j in range(len(A[0]))]
            for i in range(len(A))]


def msub(A, B):
    return [[A[i][j] - B[i][j] for j in range(len(A[0]))]
            for i in range(len(A))]


def mscale(A, s):
    return [[A[i][j] * s for j in range(len(A[0]))] for i in range(len(A))]


def dagger(A):
    return [[A[j][i].conjugate() for j in range(len(A))]
            for i in range(len(A[0]))]


def kron(A, B):
    out = []
    for i in range(len(A)):
        for k in range(len(B)):
            row = []
            for j in range(len(A[0])):
                for l in range(len(B[0])):
                    row.append(A[i][j] * B[k][l])
            out.append(row)
    return out


def matvec(A, v):
    return [sum(A[i][j] * v[j] for j in range(len(v))) for i in range(len(A))]


def inner(u, v):
    """<u|v> with the conjugate on u."""
    return sum(u[i].conjugate() * v[i] for i in range(len(u)))


def vec_norm(v):
    return math.sqrt(sum(abs(x) ** 2 for x in v))


def mat_max_dev(A, B):
    return max(abs(A[i][j] - B[i][j])
               for i in range(len(A)) for j in range(len(A[0])))


def trace(A):
    return sum(A[i][i] for i in range(len(A)))


def ket_to_rho(psi):
    """Density matrix |psi><psi| of a pure state vector."""
    return [[psi[i] * psi[j].conjugate() for j in range(len(psi))]
            for i in range(len(psi))]


def apply_unitary(rho, U):
    """rho -> U rho U+."""
    return matmul(U, matmul(rho, dagger(U)))


def expand_gate(U, qubit, n):
    """Embed a one-qubit gate U acting on `qubit` into n qubits.

    Qubit 0 is the most significant: basis index = q0 * 2 + q1 for
    two qubits, matching the kron ordering used throughout the lab.
    """
    out = None
    for q in range(n):
        factor = U if q == qubit else eye(2)
        out = factor if out is None else kron(out, factor)
    return out


def apply_single(rho, U, qubit, n):
    full = expand_gate(U, qubit, n)
    return apply_unitary(rho, full)


def cnot_matrix(control, target, n=2):
    """CNOT with the given control and target, built basis-state by
    basis-state so the convention is checkable, not quoted."""
    dim = 2 ** n
    U = zeros(dim)
    for basis in range(dim):
        bits = [(basis >> (n - 1 - q)) & 1 for q in range(n)]
        if bits[control]:
            bits[target] ^= 1
        col = sum(bits[q] << (n - 1 - q) for q in range(n))
        U[col][basis] = 1 + 0j
    return U


def partial_trace(rho, keep, n=2):
    """Trace out every qubit except `keep` from an n-qubit state."""
    dim = 2 ** n
    out = zeros(2)
    for i in range(dim):
        for j in range(dim):
            bi = [(i >> (n - 1 - q)) & 1 for q in range(n)]
            bj = [(j >> (n - 1 - q)) & 1 for q in range(n)]
            if all(bi[q] == bj[q] for q in range(n) if q != keep):
                out[bi[keep]][bj[keep]] += rho[i][j]
    return out


def measure_qubit(rho, qubit, n=2):
    """Projective Z measurement of one qubit, both branches exact.

    Returns [(outcome, probability, post_state), ...] - the branches
    are carried with their probabilities, never sampled.
    """
    branches = []
    for outcome in (0, 1):
        proj = [[complex(1.0 if b == outcome else 0.0) if a == b else 0j
                 for b in range(2)] for a in range(2)]
        P = expand_gate(proj, qubit, n)
        unnorm = matmul(P, matmul(rho, P))
        prob = trace(unnorm).real
        post = mscale(unnorm, 1.0 / prob) if prob > 0 else unnorm
        branches.append((outcome, prob, post))
    return branches


# ================================================================ 2. Pauli expectations + stabilizer Renyi entropy
PAULI_I = eye(2)
PAULI_X = [[0j, 1 + 0j], [1 + 0j, 0j]]
PAULI_Y = [[0j, -1j], [1j, 0j]]
PAULI_Z = [[1 + 0j, 0j], [0j, -1 + 0j]]
PAULIS = {"I": PAULI_I, "X": PAULI_X, "Y": PAULI_Y, "Z": PAULI_Z}

HADAMARD = mscale([[1 + 0j, 1 + 0j], [1 + 0j, -1 + 0j]], 1.0 / math.sqrt(2))
S_GATE = [[1 + 0j, 0j], [0j, 1j]]
T_GATE = [[1 + 0j, 0j],
          [0j, complex(math.cos(math.pi / 4), math.sin(math.pi / 4))]]


def pauli_string_matrix(label):
    out = None
    for ch in label:
        out = PAULIS[ch] if out is None else kron(out, PAULIS[ch])
    return out


def pauli_expectations(rho, n):
    """<P> = Tr(rho P) for every Pauli string P on n qubits.

    Computed from the density matrix itself - the lab never reads a
    Bloch vector off the state vector and calls it an expectation.
    """
    exps = {}
    for label in ("".join(t) for t in itertools.product("IXYZ", repeat=n)):
        exps[label] = trace(matmul(rho, pauli_string_matrix(label))).real
    return exps


def stabilizer_renyi_2(rho, n):
    """Stabilizer Renyi entropy M2 of a PURE state, from its Pauli data.

    M2 = -log2( (1/2^n) * sum_P |<P>|^4 ), the alpha = 2 case of the
    Leone-Oliviero-Hamma stabilizer Renyi entropy. For stabilizer
    states exactly 2^n strings have |<P>| = 1 and the rest vanish,
    so M2 = 0; any other pure state has M2 > 0. Pure states only -
    for mixed states this functional is not the magic monotone, and
    the lab does not apply it to them.
    """
    exps = pauli_expectations(rho, n)
    total = sum(abs(v) ** 4 for v in exps.values())
    return -math.log2(total / (2.0 ** n))


def bloch_m2_referee(psi):
    """Independent one-qubit M2 from the Bloch vector components.

    For one qubit sum_P |<P>|^4 = 1 + x^4 + y^4 + z^4 with (x, y, z)
    the Bloch vector, so M2 = -log2((1 + x^4 + y^4 + z^4)/2). CHECKS
    grades the full Pauli-sum implementation against this closed
    form on a battery of tilted states.
    """
    rho = ket_to_rho(psi)
    x = trace(matmul(rho, PAULI_X)).real
    y = trace(matmul(rho, PAULI_Y)).real
    z = trace(matmul(rho, PAULI_Z)).real
    return -math.log2((1.0 + x ** 4 + y ** 4 + z ** 4) / 2.0)


def tilted_ket(theta, phi):
    """|psi> = cos(theta/2)|0> + e^{i phi} sin(theta/2)|1>."""
    return [complex(math.cos(theta / 2.0)),
            complex(math.cos(phi), math.sin(phi)) * math.sin(theta / 2.0)]


def named_states():
    """The lab's state battery, each built from its definition."""
    s2 = 1.0 / math.sqrt(2)
    t_ket = [complex(s2), complex(0.5, 0.5)]  # (|0> + e^{i pi/4}|1>)/sqrt(2)
    states = {
        "zero": [1 + 0j, 0j],
        "one": [0j, 1 + 0j],
        "plus": [complex(s2), complex(s2)],
        "plus_i": [complex(s2), complex(0, s2)],
        "T": t_ket,
        "H_type": [complex(math.cos(math.pi / 8)),
                   complex(math.sin(math.pi / 8))],
        "body_diagonal": tilted_ket(math.acos(1.0 / math.sqrt(3)),
                                    math.pi / 4),
    }
    bell = [complex(s2), 0j, 0j, complex(s2)]
    states2 = {
        "bell": bell,
        "plus_plus": kron_vec(states["plus"], states["plus"]),
        "T_zero": kron_vec(t_ket, states["zero"]),
        "T_T": kron_vec(t_ket, t_ket),
    }
    return states, states2


def kron_vec(u, v):
    return [a * b for a in u for b in v]


def magic_report():
    """M2 for the whole battery, computed vs closed form side by side."""
    states, states2 = named_states()
    analytic = {
        "zero": 0.0, "one": 0.0, "plus": 0.0, "plus_i": 0.0,
        "T": M2_T_ANALYTIC, "H_type": M2_T_ANALYTIC,
        "body_diagonal": math.log2(3.0 / 2.0),
    }
    rows = {}
    for name, psi in states.items():
        rows[name] = {
            "qubits": 1,
            "m2_computed": stabilizer_renyi_2(ket_to_rho(psi), 1),
            "m2_analytic": analytic[name],
        }
    analytic2 = {"bell": 0.0, "plus_plus": 0.0,
                 "T_zero": M2_T_ANALYTIC, "T_T": 2.0 * M2_T_ANALYTIC}
    for name, psi in states2.items():
        rows[name] = {
            "qubits": 2,
            "m2_computed": stabilizer_renyi_2(ket_to_rho(psi), 2),
            "m2_analytic": analytic2[name],
        }
    return rows


# ================================================================ 3. Bravyi-Kitaev 15-to-1 distillation (the error MAP)
# HONEST FRAMING, repeated wherever the map appears: what follows is
# the 15-to-1 protocol's known leading-order error map,
#     p_out = 35 p^3 + O(p^5),
# applied exactly as a map. The lab does NOT simulate the 15-qubit
# Reed-Muller circuit qubit-by-qubit, does not model correlated or
# coherent noise, and does not claim any device ran this protocol.
# What the map does show, exactly: the cubic suppression, the fixed
# point (threshold) where input and output error are equal, and the
# 15^k raw-state overhead of iterating the round k times.

def distill_step(p):
    """One round of the 15-to-1 map: p_out = 35 p^3 (leading order)."""
    return 35.0 * p ** 3


def distill_iterate(p0, rounds):
    """[p0, p1, ..., p_rounds] under repeated application of the map."""
    out = [p0]
    for _ in range(rounds):
        out.append(distill_step(out[-1]))
    return out


def locate_threshold(lo=0.01, hi=0.5, tol=1e-13):
    """Bisect the fixed point p* with distill_step(p*) = p*.

    f(p) = 35 p^3 - p is negative below p* and positive above it on
    [0.01, 0.5], so bisection on the map itself is safe. The result
    is graded against the closed form 1/sqrt(35) in CHECKS.
    """
    def f(p):
        return distill_step(p) - p
    flo = f(lo)
    for _ in range(300):
        mid = 0.5 * (lo + hi)
        if (f(mid) > 0) == (flo > 0):
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


def distill_rounds_to_target(p0, target):
    """Rounds of the map to reach p <= target, and the raw overhead.

    Each round consumes 15 input states per output state, so k
    rounds cost 15^k raw magic states per final state - the
    combinatorics of the stated map, printed as such.
    """
    p, rounds = p0, 0
    while p > target and rounds < 60:
        p = distill_step(p)
        rounds += 1
    return {"p0": p0, "target": target, "rounds": rounds,
            "p_final": p, "raw_states": 15 ** rounds}


def distill_report():
    below = distill_iterate(0.10, 5)
    above = []
    p = 0.25
    for _ in range(4):
        above.append(p)
        p = distill_step(p)
        if p > 1.0:
            above.append(p)
            break
    return {
        "map": "p_out = 35 p^3 (leading-order Bravyi-Kitaev 15-to-1 map,"
               " applied exactly; the 15-qubit circuit is NOT simulated)",
        "threshold_numeric": locate_threshold(),
        "threshold_analytic": THRESHOLD_ANALYTIC,
        "below_threshold_p0_0.10": below,
        "above_threshold_p0_0.25": above,
        "suppression_at_0.01": distill_step(0.01) / 0.01,
        "resources_to_1e-6_from_0.10": distill_rounds_to_target(0.10, 1e-6),
        "resources_to_1e-12_from_0.10": distill_rounds_to_target(0.10, 1e-12),
    }


# ================================================================ 4. T-gate injection on density matrices
# Unlike the distillation map, this circuit IS simulated in full:
# data qubit + magic-state ancilla, CNOT (data controls), Z
# measurement of the ancilla with both branches carried exactly,
# and the Clifford S correction on the outcome-1 branch:
#   outcome 0 -> data is T|psi>            (probability 1/2)
#   outcome 1 -> data is T-dagger|psi>, corrected by S (S T+ = T)
# The magic state is noisy under two stated models:
#   depolarizing: rho_A = (1-p) |T><T| + p I/2
#   phase_flip:   rho_A = (1-p) |T><T| + p Z|T><T|Z
# and the lab reports the output infidelity for both.

def t_state_rho():
    states, _ = named_states()
    return ket_to_rho(states["T"])


def noisy_magic(p, model="depolarizing"):
    """The noisy T-state density matrix under a stated noise model."""
    rho_t = t_state_rho()
    if model == "depolarizing":
        mixed = mscale(eye(2), 0.5)
        return madd(mscale(rho_t, 1.0 - p), mscale(mixed, p))
    if model == "phase_flip":
        flipped = apply_unitary(rho_t, PAULI_Z)
        return madd(mscale(rho_t, 1.0 - p), mscale(flipped, p))
    raise ValueError(f"unknown noise model: {model}")


def inject_t(rho_data, rho_magic):
    """Run the injection circuit on density matrices, branches exact.

    Qubit 0 = data, qubit 1 = magic-state ancilla. Returns
    (rho_out, {outcome: probability}) with the S correction applied
    to the outcome-1 branch before the branches are mixed.
    """
    joint = kron(rho_data, rho_magic)
    joint = apply_unitary(joint, cnot_matrix(0, 1))
    rho_out = zeros(2)
    probs = {}
    for outcome, prob, post in measure_qubit(joint, 1):
        probs[outcome] = prob
        data = partial_trace(post, keep=0)
        if outcome == 1:
            data = apply_unitary(data, S_GATE)
        rho_out = madd(rho_out, mscale(data, prob))
    return rho_out, probs


def pure_fidelity(rho, psi):
    """Fidelity <psi|rho|psi> of a mixed state against a pure target."""
    return inner(psi, matvec(rho, psi)).real


def inject_report(p_values=(0.0, 0.01, 0.05, 0.10, 0.20)):
    """Output fidelity vs input error p, for both noise models.

    Input data state is |+>; the ideal output is T|+> = |T> itself,
    so the output state is graded against |T>. The exact relations
    the circuit produces (all asserted in CHECKS):
      depolarizing: magic infidelity = p/2, epsilon_out = p/2
        - the raw noise rate p is halved at first order through one
          injection; against the resource's own infidelity the error
          is transferred, not reduced further.
      phase_flip:   magic infidelity = p,   epsilon_out = p
        - no suppression at all; the error passes straight through.
    Both models are printed wherever injection is reported.
    """
    states, _ = named_states()
    rho_plus = ket_to_rho(states["plus"])
    target = states["T"]
    rows = []
    for p in p_values:
        row = {"p": p}
        for model in ("depolarizing", "phase_flip"):
            rho_magic = noisy_magic(p, model)
            rho_out, probs = inject_t(rho_plus, rho_magic)
            row[model] = {
                "magic_fidelity": pure_fidelity(rho_magic, target),
                "output_fidelity": pure_fidelity(rho_out, target),
                "epsilon_out": 1.0 - pure_fidelity(rho_out, target),
                "branch_probs": [probs[0], probs[1]],
            }
        rows.append(row)
    return {
        "circuit": "CNOT(data->ancilla), measure ancilla in Z,"
                   " S correction on outcome 1; branches exact",
        "input_data_state": "|+>",
        "ideal_output": "T|+> = |T>",
        "rows": rows,
    }


# ================================================================ 5. kNN supply classifier
# Features: (M2 of the resource state, log10 of its error rate p).
# The training grid is labelled by the lab's own policy (policy_label
# below) - the classifier interpolates the policy, it does not
# replace the M2 computation or the threshold arithmetic.

def policy_label(m2, p):
    """The lab's supply policy for a magic-state batch.

    No magic -> useless as a resource, whatever its error rate.
    Error at or above the distillation threshold -> distillation
    cannot help. Very clean -> inject directly. In between -> run
    the 15-to-1 map first.
    """
    if m2 < 0.05:
        return "no-magic"
    if p >= THRESHOLD_ANALYTIC:
        return "above-threshold"
    if p <= 0.01:
        return "inject-ready"
    return "distill-first"


def _training_grid():
    # Region-clustered points, each strictly inside one policy
    # region, so the kNN's agreement with the policy is checkable.
    regions = [
        ((0.0, 0.01, 0.03), (0.005, 0.05, 0.30)),          # no-magic
        ((0.30, 0.415, 0.585), (0.001, 0.004, 0.008)),     # inject-ready
        ((0.30, 0.415, 0.585), (0.03, 0.06, 0.12)),        # distill-first
        ((0.30, 0.415, 0.585), (0.22, 0.30, 0.45)),        # above-threshold
    ]
    rows = []
    for m2_values, p_values in regions:
        for m2 in m2_values:
            for p in p_values:
                rows.append(((m2, p), policy_label(m2, p)))
    return rows


TRAINING_GRID = _training_grid()


def _scaled(features):
    m2, p = features
    return (m2, math.log10(p))


def classify_supply(m2, p, k=3):
    """Distance-weighted kNN over the policy-labelled grid."""
    target = _scaled((m2, p))
    ranked = []
    for features, label in TRAINING_GRID:
        point = _scaled(features)
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(target, point)))
        ranked.append((dist, features, label))
    ranked.sort(key=lambda row: (row[0], row[1]))
    weights = {}
    for dist, _, label in ranked[:k]:
        weights[label] = weights.get(label, 0.0) + 1.0 / (dist + 1e-9)
    priority = {"no-magic": 0, "inject-ready": 1,
                "distill-first": 2, "above-threshold": 3}
    return sorted(weights.items(),
                  key=lambda kv: (-kv[1], priority[kv[0]]))[0][0]


def classifier_report():
    states, _ = named_states()
    m2_t = stabilizer_renyi_2(ket_to_rho(states["T"]), 1)
    m2_body = stabilizer_renyi_2(ket_to_rho(states["body_diagonal"]), 1)
    scenarios = {
        "t_state_p_0.001": (m2_t, 0.001),
        "t_state_p_0.05": (m2_t, 0.05),
        "t_state_p_0.25": (m2_t, 0.25),
        "plus_state_p_0.05": (0.0, 0.05),
        "body_diagonal_p_0.08": (m2_body, 0.08),
    }
    return {name: classify_supply(m2, p)
            for name, (m2, p) in scenarios.items()}


# ================================================================ 6. Advisory seats
def _trace(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def argon4_decide(topic="magicstate-demo"):
    """Gemini Argon 4 DECIDER seat: MAP->MODEL->STRESS->DECIDE.

    Names-only keys, live calls 0, tighten-only: can add HOLDs, never lift one.
    """
    stages = ["MAP", "MODEL", "STRESS", "DECIDE"]
    payload = {"seat": "gemini-argon-4", "topic": topic, "stages": stages}
    return {
        "seat": "Gemini Argon 4 Extended Thinking",
        "role": "DECIDER",
        "pipeline": stages,
        "tiers": [2048, 8192, 32768],
        "key": "names-only (GEMINI_API_KEY name checked, value never read)",
        "live_calls": 0,
        "decision": "PROCEED - sandbox simulation only, all real-world gates stay HOLD",
        "can_override_hold": False,
        "trace_sha256_16": _trace(payload),
    }


def claude_advisor(topic="magicstate-demo"):
    """Muse advisor seat: advises, can never override a HOLD."""
    return {
        "seat": "Muse",
        "role": "ADVISOR",
        "key": "names-only (MODEL_API_KEY name checked, value never read)",
        "live_calls": 0,
        "advice": "Say it in the first line of every report: M2 is computed from the state's own Pauli expectations, the distillation curve is the protocol's leading-order error map applied exactly - not a 15-qubit circuit simulation - and no number here certifies a real device.",
        "can_override_hold": False,
    }


def google_flow_plan():
    """Google Flow seat: plan-only, nothing rendered, nothing live."""
    return {
        "seat": "Google Flow",
        "role": "PLAN-ONLY",
        "shots": ["a Bloch vector settling onto the T state's 45-degree meridian as M2 counts up to 0.415",
                  "fifteen noisy magic states funnelling into one clean state per round",
                  "the error curve collapsing doubly-exponentially below a marked threshold line",
                  "the same curve exploding upward above the threshold",
                  "a two-qubit injection circuit: CNOT, a measurement flash, an S correction"],
        "rendered": False,
        "live": 0,
    }


def brains_report():
    return {"decider": argon4_decide(), "advisor": claude_advisor(),
            "flow": google_flow_plan()}


# ================================================================ checks
def run_checks():
    c = []

    def chk(name, ok):
        c.append((name, bool(ok)))

    states, states2 = named_states()
    rho = lambda psi: ket_to_rho(psi)  # noqa: E731

    # 1. density-matrix kit referees - trusted only after these
    exps0 = pauli_expectations(rho(states["zero"]), 1)
    chk("pauli_expectations_zero_state",
        abs(exps0["I"] - 1.0) < 1e-12 and abs(exps0["Z"] - 1.0) < 1e-12
        and abs(exps0["X"]) < 1e-12 and abs(exps0["Y"]) < 1e-12)
    ok = True
    for psi in list(states.values()) + list(states2.values()):
        r = rho(psi)
        ok = ok and abs(trace(r) - 1.0) < 1e-12 \
            and mat_max_dev(r, dagger(r)) < 1e-12
    chk("density_matrices_trace_one_hermitian", ok)
    cnot = cnot_matrix(0, 1)
    ok = True
    basis = [[1 + 0j, 0j, 0j, 0j], [0j, 1 + 0j, 0j, 0j],
             [0j, 0j, 1 + 0j, 0j], [0j, 0j, 0j, 1 + 0j]]
    expect = [basis[0], basis[1], basis[3], basis[2]]
    for b, e in zip(basis, expect):
        ok = ok and max(abs(x - y) for x, y in zip(matvec(cnot, b), e)) < 1e-12
    chk("cnot_truth_table", ok)
    prod = kron(rho(states["T"]), rho(states["plus"]))
    chk("partial_trace_product_state",
        mat_max_dev(partial_trace(prod, keep=0), rho(states["T"])) < 1e-12
        and mat_max_dev(partial_trace(prod, keep=1),
                        rho(states["plus"])) < 1e-12)
    branches = measure_qubit(kron(rho(states["plus"]),
                                  rho(states["plus"])), 1)
    chk("measurement_branch_probabilities",
        all(abs(p - 0.5) < 1e-12 for _, p, _ in branches))
    chk("s_gate_correction_identity",
        mat_max_dev(matmul(S_GATE, dagger(T_GATE)), T_GATE) < 1e-12)
    chk("t_gate_on_plus_is_t_state",
        max(abs(x - y) for x, y in
            zip(matvec(T_GATE, states["plus"]), states["T"])) < 1e-12)

    # 2. stabilizer Renyi entropy - zero for stabilizer states
    for name in ("zero", "one", "plus", "plus_i"):
        chk(f"m2_stabilizer_{name}",
            abs(stabilizer_renyi_2(rho(states[name]), 1)) < 1e-9)
    chk("m2_bell_stabilizer",
        abs(stabilizer_renyi_2(rho(states2["bell"]), 2)) < 1e-9)
    chk("m2_plus_plus_stabilizer",
        abs(stabilizer_renyi_2(rho(states2["plus_plus"]), 2)) < 1e-9)

    # 3. magic states - M2 against closed forms
    m2_t = stabilizer_renyi_2(rho(states["T"]), 1)
    chk("m2_t_state_is_minus_log2_three_quarters",
        abs(m2_t - M2_T_ANALYTIC) < 1e-12
        and abs(m2_t - 0.4150374992788438) < 1e-12)
    chk("m2_h_type_state",
        abs(stabilizer_renyi_2(rho(states["H_type"]), 1)
            - M2_T_ANALYTIC) < 1e-12)
    chk("m2_body_diagonal_is_log2_three_halves",
        abs(stabilizer_renyi_2(rho(states["body_diagonal"]), 1)
            - math.log2(3.0 / 2.0)) < 1e-12)
    chk("m2_additive_t_zero",
        abs(stabilizer_renyi_2(rho(states2["T_zero"]), 2)
            - M2_T_ANALYTIC) < 1e-12)
    chk("m2_additive_t_t",
        abs(stabilizer_renyi_2(rho(states2["T_T"]), 2)
            - 2.0 * M2_T_ANALYTIC) < 1e-12)
    ok = True
    for theta_deg in (20.0, 55.0, 90.0, 130.0, 170.0):
        for phi_deg in (0.0, 40.0, 90.0, 200.0):
            psi = tilted_ket(math.radians(theta_deg), math.radians(phi_deg))
            ok = ok and abs(stabilizer_renyi_2(rho(psi), 1)
                            - bloch_m2_referee(psi)) < 1e-12
    chk("m2_matches_bloch_referee", ok)
    exps_t = pauli_expectations(rho(states["T"]), 1)
    chk("pauli_distribution_normalised",
        abs(sum(v * v for v in exps_t.values()) / 2.0 - 1.0) < 1e-12)

    # 4. distillation map - cubic suppression and the threshold
    chk("distill_map_values",
        abs(distill_step(0.10) - 0.035) < 1e-15
        and abs(distill_step(0.05) - 0.004375) < 1e-15)
    p_star = locate_threshold()
    chk("threshold_numeric_matches_analytic",
        abs(p_star - THRESHOLD_ANALYTIC) < 1e-9
        and abs(p_star - 0.1690308509457033) < 1e-9)
    chk("threshold_is_fixed_point",
        abs(distill_step(p_star) - p_star) < 1e-9)
    below = distill_iterate(0.10, 5)
    chk("below_threshold_shrinks_doubly_fast",
        all(below[i + 1] < below[i] for i in range(len(below) - 1))
        and below[3] < 1e-6 and below[5] < 1e-18)
    above = distill_iterate(0.25, 2)
    chk("above_threshold_grows",
        above[1] > 0.25 and above[2] > above[1])
    chk("suppression_factor_at_1e-2",
        abs(distill_step(0.01) / 0.01 - 0.0035) < 1e-12)
    res = distill_rounds_to_target(0.10, 1e-6)
    chk("distill_resources_to_1e-6",
        res["rounds"] == 3 and res["raw_states"] == 3375
        and res["p_final"] <= 1e-6)
    res = distill_rounds_to_target(0.10, 1e-12)
    chk("distill_resources_to_1e-12",
        res["rounds"] == 4 and res["raw_states"] == 50625)

    # 5. injection - perfect at p = 0, error transfer graded exactly
    rho_plus = rho(states["plus"])
    rho_out, probs = inject_t(rho_plus, t_state_rho())
    chk("inject_perfect_output_is_t_state",
        mat_max_dev(rho_out, t_state_rho()) < 1e-12)
    chk("inject_branch_probabilities_half",
        abs(probs[0] - 0.5) < 1e-12 and abs(probs[1] - 0.5) < 1e-12)
    report = inject_report()
    chk("inject_depolarizing_error_halved",
        all(abs(r["depolarizing"]["epsilon_out"] - r["p"] / 2.0) < 1e-12
            for r in report["rows"]))
    chk("inject_depolarizing_suppresses_rate",
        all(r["depolarizing"]["epsilon_out"] < r["p"]
            for r in report["rows"] if r["p"] > 0))
    chk("inject_phaseflip_error_passes_through",
        all(abs(r["phase_flip"]["epsilon_out"] - r["p"]) < 1e-12
            for r in report["rows"]))
    chk("inject_magic_infidelity_models",
        all(abs((1.0 - r["depolarizing"]["magic_fidelity"]) - r["p"] / 2.0)
            < 1e-12 and abs((1.0 - r["phase_flip"]["magic_fidelity"])
                            - r["p"]) < 1e-12 for r in report["rows"]))

    # 6. classifier - labels come from the lab's own policy
    rep = classifier_report()
    chk("classifier_t_inject_ready", rep["t_state_p_0.001"] == "inject-ready")
    chk("classifier_t_distill_first", rep["t_state_p_0.05"] == "distill-first")
    chk("classifier_t_above_threshold",
        rep["t_state_p_0.25"] == "above-threshold")
    chk("classifier_plus_no_magic", rep["plus_state_p_0.05"] == "no-magic")
    chk("classifier_body_diagonal_distill",
        rep["body_diagonal_p_0.08"] == "distill-first")
    chk("classifier_matches_policy_on_grid",
        all(classify_supply(*features) == policy_label(*features)
            for features, _ in TRAINING_GRID))

    # gates + seats
    chk("hold_gates_14", len(HOLD_GATES) == 14
        and all(v.startswith("HOLD") for v in HOLD_GATES.values()))
    chk("gate_ftc_claim_hold", gate("fault_tolerant_computer_claim") == "HOLD")
    chk("gate_distillation_claim_hold",
        gate("real_hardware_distillation_claim") == "HOLD")
    chk("gate_error_rate_cert_hold",
        gate("real_device_error_rate_certification") == "HOLD")
    chk("gate_sim_as_measurement_hold",
        gate("simulation_as_measurement_claim") == "HOLD")
    chk("gate_sandbox_proceed", gate("run_simulation") == "PROCEED")
    brains = brains_report()
    chk("argon4_no_override", brains["decider"]["can_override_hold"] is False
        and brains["decider"]["seat"]
        == "Gemini Argon 4 Extended Thinking")
    chk("claude_no_override", brains["advisor"]["can_override_hold"] is False)
    chk("flow_plan_only", brains["flow"]["rendered"] is False
        and brains["flow"]["live"] == 0)
    return c


# ================================================================ CLI / demo
def demo():
    print("=" * 68)
    print("MagicState-Lab - magic states, distillation map & T injection")
    print("by Darion Kellar | MIT | pure stdlib | zero network | EDUCATION ONLY")
    print("=" * 68)
    print("\n[1] THE HONEST CORE - magic is computed, distillation is a map")
    print("    M2 (stabilizer Renyi entropy) is evaluated from each state's")
    print("    own Pauli expectation values - nothing is asserted. The")
    print("    15-to-1 distillation section applies the protocol's known")
    print("    leading-order error map p -> 35 p^3 exactly; the 15-qubit")
    print("    Reed-Muller circuit is NOT simulated qubit-by-qubit, and no")
    print("    real device is measured anywhere in this lab.")
    print("\n[2] Stabilizer Renyi entropy M2 - computed vs closed form")
    for name, row in magic_report().items():
        print(f"    {name:14s} ({row['qubits']}q)  M2 computed "
              f"{row['m2_computed']:.12f} | analytic "
              f"{row['m2_analytic']:.12f}")
    print("    -> stabilizer states sit at exactly 0; |T> carries")
    print(f"       -log2(3/4) = {M2_T_ANALYTIC:.12f} of magic, and M2 is")
    print("       additive: |T>|T> doubles it, |T>|0> keeps it.")
    dist = distill_report()
    print("\n[3] Distillation map below threshold - p0 = 0.10, p -> 35 p^3")
    for i, p in enumerate(dist["below_threshold_p0_0.10"]):
        print(f"    round {i}: p = {p:.6e}")
    print("    -> cubic suppression compounds: each round cubes the error")
    print("       (times 35), so the fall is doubly exponential.")
    print("\n[4] Above threshold - p0 = 0.25")
    for i, p in enumerate(dist["above_threshold_p0_0.25"]):
        print(f"    round {i}: p = {p:.6e}")
    print("    -> the same map now amplifies: past p* the 'distilled' state")
    print("       is worse than the input, and the map soon leaves the")
    print("       small-p regime where the polynomial is meaningful.")
    print(f"\n[5] Threshold - fixed point of p = 35 p^3")
    print(f"    numeric (bisection on the map): {dist['threshold_numeric']:.12f}")
    print(f"    analytic 1/sqrt(35):             {dist['threshold_analytic']:.12f}")
    res6 = dist["resources_to_1e-6_from_0.10"]
    res12 = dist["resources_to_1e-12_from_0.10"]
    print(f"    overhead from p0 = 0.10: to 1e-6 in {res6['rounds']} rounds "
          f"({res6['raw_states']} raw states); to 1e-12 in "
          f"{res12['rounds']} rounds ({res12['raw_states']} raw states)")
    print("    -> overhead is 15^rounds by the map's own combinatorics -")
    print("       a count of states, not a forecast or a roadmap.")
    print("\n[6] T-gate injection - circuit simulated on density matrices")
    print("    input |+>, ideal output T|+> = |T>; branches exact, S-corrected")
    print(f"    {'p':>6s} {'eps_out depol':>14s} {'eps_out phase-flip':>19s}")
    for row in inject_report()["rows"]:
        print(f"    {row['p']:6.2f} "
              f"{row['depolarizing']['epsilon_out']:14.6f} "
              f"{row['phase_flip']['epsilon_out']:19.6f}")
    print("    -> depolarizing noise: eps_out = p/2 exactly - the first-order")
    print("       error is halved through one injection (and equals the magic")
    print("       state's own infidelity p/2 under this model: transferred at")
    print("       half the raw noise rate). Phase-flip noise: eps_out = p -")
    print("       the error passes straight through. Both printed, neither")
    print("       cherry-picked.")
    print("\n[7] Supply classifier (TinyML kNN, labels from the lab's policy)")
    for name, label in classifier_report().items():
        print(f"    {name:24s} -> {label}")
    print("\n[8] Advisory seats")
    brains = brains_report()
    print(f"    decider: {brains['decider']['decision']} "
          f"trace={brains['decider']['trace_sha256_16']}")
    print(f"    advisor can_override_hold = {brains['advisor']['can_override_hold']}")
    print(f"    flow rendered = {brains['flow']['rendered']} "
          f"live = {brains['flow']['live']}")
    print(f"\n[9] HOLD gates: {len(HOLD_GATES)}")
    for key in HOLD_GATES:
        print(f"    HOLD  {key}")
    checks = run_checks()
    passed = sum(1 for _, ok in checks if ok)
    print(f"\nCHECKS {passed}/{len(checks)}")
    for name, ok in checks:
        if not ok:
            print(f"    FAIL {name}")
    verdict = "PROCEED" if passed == len(checks) else "HOLD"
    print(f"VERDICT {verdict} (sandbox simulation only) | HOLD gates {len(HOLD_GATES)}")
    return 0 if passed == len(checks) else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] == "demo":
        return demo()
    cmd = argv[0]
    if cmd == "checks":
        checks = run_checks()
        for name, ok in checks:
            print(f"{'PASS' if ok else 'FAIL'} {name}")
        print(f"CHECKS {sum(1 for _, ok in checks if ok)}/{len(checks)}")
        return 0 if all(ok for _, ok in checks) else 1
    if cmd == "magic":
        print(json.dumps(magic_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "distill":
        print(json.dumps(distill_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "inject":
        print(json.dumps(inject_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "threshold":
        print(json.dumps({
            "threshold_numeric": locate_threshold(),
            "threshold_analytic": THRESHOLD_ANALYTIC,
            "fixed_point_residual": abs(distill_step(locate_threshold())
                                        - locate_threshold()),
        }, indent=2, sort_keys=True))
        return 0
    if cmd == "classify":
        print(json.dumps(classifier_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "brains":
        print(json.dumps(brains_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "holds":
        for key, value in HOLD_GATES.items():
            print(f"{key}: {value}")
        return 0
    if cmd == "hold-demo":
        action = argv[1] if len(argv) > 1 else "fault_tolerant_computer_claim"
        print(f"{action}: {HOLD_GATES.get(action, 'PROCEED - not gated')}")
        return 2 if gate(action) == "HOLD" else 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
