"""Various helper functions for the command-line interface."""

import argparse
import ast
import sys
from typing import Any, Dict, List, Type

from rocket_controller.strategies import Strategy


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.

    Returns:
        An argparse namespace object, containing the parsed arguments.
    """
    parser = argparse.ArgumentParser(
        prog="python -m rocket_controller",
        description="A tool for testing the XRP Ledger consensus algorithm at the system-level, "
        "using easily adaptable fuzzing-based techniques.",
    )
    parser.add_argument(
        "strategy",
        type=str,
        default="RandomFuzzer",
        help="The name of the Strategy Class to use.",
    )
    parser.add_argument(
        "-n",
        "--network_config",
        type=str,
        default=None,
        help="The relative path to the network configuration file to use. "
        "Defaults to ./config/default_network.yaml.",
        metavar="PATH",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        help="The relative path to the configuration file to use. Defaults to ./config/default_NAME.yaml, "
        "e.g. for the RandomFuzzer, the default would be ./config/default_RandomFuzzer.yaml",
        metavar="PATH",
    )
    parser.add_argument(
        "--nodes",
        type=int,
        default=None,
        help="The amount of XRPL validator nodes to configure in the network. "
        "If set, overrides the amount of nodes specified in the network configuration file.",
        metavar="AMOUNT",
    )
    parser.add_argument(
        "--partition",
        type=check_valid_partition,
        default=None,
        help="The network partition of the nodes. "
        "If set, overrides the partition specified in the network configuration file.",
        metavar="PARTITION",
    )
    parser.add_argument(
        "--nodes_unl",
        type=check_valid_partition,
        default=None,
        help="The UNL (trusted nodes) configuration. "
        "If set, overrides the UNL partition specified in the network configuration file.",
        metavar="UNL",
    )
    parser.add_argument(
        "--overrides",
        type=check_valid_strategy_overrides,
        default=None,
        help="A way to override certain values found in the strategy configuration file. "
        "Format: PARAM1=VALUE1,PARAM2=VALUE2...",
        metavar="VALUES",
    )

    return parser.parse_args()


def str_to_strategy(classname: str) -> Type[Strategy]:
    """
    Returns a Strategy class type based on the name of the Strategy.

    Args:
        classname: The name of the Strategy class.

    Returns:
        A Strategy class type.
    """
    return getattr(sys.modules["rocket_controller.strategies"], classname)


def check_valid_partition(partition: str) -> List[List[int]]:
    """
    Checks whether the string format of a network partition is valid.

    Args:
        partition: The string containing the network partition.

    Returns:
        A 2d list containing the network partition.
    """

    def valid_2d_array(array) -> bool:
        if isinstance(array, list):
            return all(isinstance(i, list) for i in array)
        return False

    try:
        parsed_array = ast.literal_eval(partition)
        if valid_2d_array(parsed_array):
            return parsed_array
        raise ValueError
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"not a valid partition: {partition!r}") from e


def check_valid_strategy_overrides(overrides_str: str) -> Dict[str, str]:
    """
    Checks whether the string format of network parameter overrides is valid.

    Args:
        overrides_str: The string containing the network parameter overrides.

    Returns:
        A dictionary containing the key-value pairs for the network parameter overrides.
    """
    result = {}
    items = overrides_str.split(",")
    for item in items:
        separated_items = item.split("=")
        if len(separated_items) != 2:
            raise argparse.ArgumentTypeError(f"not a valid override: {item!r}")
        result[separated_items[0]] = separated_items[1]
    return result


def process_args(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Parses the command line arguments.

    Args:
        args: The command line arguments.

    Returns:
        A dictionary containing the (overridden) class parameters for a Strategy instance.
    """
    params_dict = {}
    network_overrides = {}

    if args.nodes:
        network_overrides["number_of_nodes"] = args.nodes
    if args.partition:
        network_overrides["network_partition"] = args.partition
    if args.nodes_unl:
        network_overrides["unl_partition"] = args.nodes_unl

    if args.network_config:
        params_dict["network_config_path"] = args.network_config
    if args.config:
        params_dict["strategy_config_path"] = args.config
    if len(network_overrides.keys()) > 0:
        params_dict["network_overrides"] = network_overrides
    if args.overrides and len(args.overrides.keys()) > 0:
        params_dict["strategy_overrides"] = args.overrides

    return params_dict
