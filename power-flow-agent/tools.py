# tools.py

import pandapower as pp
import pandapower.networks as pn
import matplotlib.pyplot as plt


# -----------------------------
# Case Loader Tool
# -----------------------------
def load_test_case(case_name: str):
    case_name = case_name.lower()

    if "14" in case_name:
        net = pn.case14()
    elif "30" in case_name:
        net = pn.case30()
    elif "57" in case_name:
        net = pn.case57()
    else:
        raise ValueError("Unsupported test case")

    return net


# -----------------------------
# Power Flow Solver Tool
# -----------------------------
def run_power_flow(net):
    try:
        pp.runpp(net)
        return net
    except Exception as e:
        raise RuntimeError(f"Power flow failed: {e}")


# -----------------------------
# Result Extraction Tool
# -----------------------------
def extract_results(net):
    results = {
        "bus_voltages": net.res_bus.vm_pu.to_dict(),
        "line_loading_percent": net.res_line.loading_percent.to_dict(),
        "line_p_from_mw": net.res_line.p_from_mw.to_dict(),
        "converged": net.converged
    }
    return results