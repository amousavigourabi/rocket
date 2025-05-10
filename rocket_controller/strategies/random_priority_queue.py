"""This module contains the class that implements a random priority queue."""

import random
from typing import Any, Dict, Tuple

from protos import packet_pb2
from rocket_controller.helper import MAX_U32
from rocket_controller.iteration_type import TimeBasedIteration, LedgerBasedIteration
from rocket_controller.strategies.strategy import Strategy


class RandomPriorityQueue(Strategy):
    """Class that implements a random fuzzer."""

    def __init__(
        self,
        network_config_path: str = "./config/network/default_network.yaml",
        strategy_config_path: str | None = None,
        auto_parse_identical: bool = True,
        auto_parse_subsets: bool = True,
        iteration_type: TimeBasedIteration | None = LedgerBasedIteration(10, 10, 60),
        network_overrides: Dict[str, Any] | None = None,
        strategy_overrides: Dict[str, Any] | None = None,
    ):
        """
        Initializes the random priority queue.

        Args:
            network_config_path: The path to a network config file to be used.
            strategy_config_path: The path to a strategy config file to be used.
            auto_parse_identical: Whether to auto-parse identical packages per peer combination.
            auto_parse_subsets: Whether to auto-parse identical packages w.r.t. defined subsets.
            iteration_type: The type of iteration to keep track of.
            network_overrides: A dictionary containing parameter names and values which override the network config.
            strategy_overrides: A dictionary containing parameter names and values which override the strategy config.

        Raises:
            ValueError: If retrieved probabilities or delays are invalid.
        """
        super().__init__(
            network_config_path=network_config_path,
            strategy_config_path=strategy_config_path,
            auto_parse_identical=auto_parse_identical,
            auto_parse_subsets=auto_parse_subsets,
            iteration_type=iteration_type,
            network_overrides=network_overrides,
            strategy_overrides=strategy_overrides,
        )

        if self.params["seed"] is not None:
            random.seed(self.params["seed"])

        # Validate required parameters exist
        required_params = [
            "min_priority",
            "max_priority",
            "target_inbox",
            "overflow_factor",
            "underflow_factor",
            "sensitivity_ratio",
            "max_events",
            "priority_list"
        ]

        missing_params = [param for param in required_params if param not in self.params]
        if missing_params:
            raise ValueError(f"Missing required parameters in configuration: {', '.join(missing_params)}")

        # Validate numeric parameters and their ranges
        try:
            self.min_priority = int(self.params.get("min_priority"))
            self.max_priority = int(self.params.get("max_priority"))
            self.target_inbox = int(self.params.get("target_inbox"))
            self.overflow_factor = float(self.params.get("overflow_factor"))
            self.underflow_factor = float(self.params.get("underflow_factor"))
            self.sensitivity_ratio = float(self.params.get("sensitivity_ratio"))
            self.max_events = int(self.params.get("max_events"))
        except ValueError as e:
            raise ValueError("Invalid numeric value in configuration") from e

        # Validate value ranges
        if self.min_priority < 0:
            raise ValueError(f"min_priority must be non-negative, got {self.min_priority}")
        if self.max_priority <= self.min_priority:
            raise ValueError(
                f"max_priority ({self.max_priority}) must be greater than min_priority ({self.min_priority})")
        if self.target_inbox <= 0:
            raise ValueError(f"target_inbox must be positive, got {self.target_inbox}")
        if self.overflow_factor <= 1:
            raise ValueError(f"overflow_factor must be greater than 1, got {self.overflow_factor}")
        if self.underflow_factor >= 1:
            raise ValueError(f"underflow_factor must be less than 1, got {self.underflow_factor}")
        if self.sensitivity_ratio <= 1:
            raise ValueError(f"sensitivity_ratio must be greater than 1, got {self.sensitivity_ratio}")
        if self.max_events <= 0:
            raise ValueError(f"max_events must be positive, got {self.max_events}")

    def setup(self):
        """Setup method for RandomFuzzer."""

    def handle_packet(self, packet: packet_pb2.Packet) -> Tuple[bytes, int, int]:
        """
        Implements the handle_packet method with a random action.

        Args:
            packet: The original packet to be sent.

        Returns:
            Tuple[bytes, int, int]: The new packet, the random action and the send amount.
        """
        choice: float = random.random()
        if choice < self.params["send_probability"]:
            return packet.data, 0, 1
        elif choice < self.params["send_probability"] + self.params["drop_probability"]:
            return packet.data, MAX_U32, 1
        else:
            return (
                packet.data,
                random.randint(
                    self.params["min_delay_ms"], self.params["max_delay_ms"]
                ),
                1,
            )
