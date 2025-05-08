"""This module contains the SpecChecker class, which is used to perform specification checks on the results of the iterations."""

import csv
import json
from collections import defaultdict
from typing import Any, List

from loguru import logger

from rocket_controller.consensus_properties import ConsensusProperties
from rocket_controller.csv_logger import SpecCheckLogger

from collections import defaultdict

class SpecChecker:
    """Class to perform specification checks on the results of the iterations."""

    def __init__(self, log_dir: str):
        """Initialize the SpecChecker object.

        Args:
            log_dir: The directory where the spec check results will be stored.
        """
        self.spec_check_logger: SpecCheckLogger = SpecCheckLogger(log_dir)
        self.log_dir: str = log_dir

    def read_results_log(self, result_file_path: str, iteration: int) -> dict[int, list[dict]]:
        ledgers_data = defaultdict(list)
        try:
            with open(result_file_path) as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # Basic type conversion and validation
                    try:
                        node_id = int(row["node_id"])
                        ledger_seq = int(row["ledger_seq"])
                        goal_ledger_seq = int(row["goal_ledger_seq"])
                        ledger_hash = row["ledger_hash"]
                        ledger_index = int(row["ledger_index"])
                        parsed_row = {
                            "node_id": node_id,
                            "ledger_seq": ledger_seq,
                            "goal_ledger_seq": goal_ledger_seq,
                            "ledger_hash": ledger_hash,
                            "ledger_index": ledger_index,
                        }
                        ledgers_data[ledger_seq].append(parsed_row)
                    except (ValueError, KeyError) as e:
                        logger.error(f"Skipping row due to parsing error: {e} in row: {row}")
                        continue
        except csv.Error as e:
            logger.critical(f"CSV Results Error: {e}")
            self.spec_check_logger.log_spec_check(
                iteration, f"CSV Results Error: {e}", "-", "-", "-", "-"
            )
        return ledgers_data
    def read_actions_log(self, actions_file_path: str, iteration: int) -> dict[int, list[dict]]:
        actions_data = defaultdict(list)
        try:
            with open(actions_file_path, newline="") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    try:
                        timestamp = int(row["timestamp"])
                        action = int(row["action"])
                        from_node_id = int(row["from_node_id"])
                        to_node_id = int(row["to_node_id"])
                        message_type = row["message_type"]
                        original_data = row["original_data"]
                        possibly_mutated_data = row["possibly_mutated_data"]

                        if message_type == "TMProposeSet":
                            parsed_propose_set = self.parse_tmproposeset_message(original_data)
                            proto_obj = parsed_propose_set
                        elif message_type == "TMStatusChange":
                            parsed_status_change = self.parse_tmstatuschange_message(original_data)
                            proto_obj = parsed_status_change
                        else:
                            proto_obj = None
                        
                        actions_data[from_node_id].append({
                            "timestamp": timestamp,
                            "action": action,
                            "to_node_id": to_node_id,
                            "message_type": message_type,
                            "protobuf_obj": proto_obj,
                            "possibly_mutated_data": possibly_mutated_data,
                        })
                    except Exception as e:
                        logger.error(
                            f"Skipping row due to parsing error: {e} in row: {row}"
                        )
                        continue
        except csv.Error as e:
            logger.critical(f"CSV Action Error: {e}")
            self.spec_check_logger.log_spec_check(
                iteration, f"CSV Action Error: {e}", "-", "-", "-", "-"
            )
        return actions_data

    def parse_tmstatuschange_message(self, message: str) -> dict:
        parsed_data = {}
        try:
            pairs = message.split(";")
            for pair in pairs:
                if ":" in pair:
                    key, value = pair.split(":", 1)
                    key = key.strip()
                    value = value.strip()

                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]

                    if value.isdigit():
                        value = int(value)

                    parsed_data[key] = value
        except Exception as e:
            logger.error(f"Error parsing TMStatusChange message: {e}")
        return parsed_data
    
    def parse_tmproposeset_message(self, message: str) -> dict:
        parsed_data = {}
        try:
            pairs = message.split(";")
            for pair in pairs:
                if ":" in pair:
                    key, value = pair.split(":", 1)
                    key = key.strip()
                    value = value.strip()

                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]

                    if value.isdigit():
                        value = int(value)

                    parsed_data[key] = value
        except Exception as e:
            logger.error(f"Error parsing TMProposeSet message: {e}")
        return parsed_data
    
    def spec_check(self, iteration: int):
        """
        Do a specification check for the current iteration and log the results.

        Args:
            iteration: The current iteration.
        """
        result_file_path = (
            f"logs/{self.log_dir}/iteration-{iteration}/result-{iteration}.csv"
        )
        ledgers_data = self.read_results_log(result_file_path, iteration)
        if not ledgers_data:
            logger.critical("No valid ledger data found.")
            self.spec_check_logger.log_spec_check(
                iteration, "No valid ledger data found.", "-", "-", "-", "-"
            )
            return
        
        actions_file_path = (
            f"logs/{self.log_dir}/iteration-{iteration}/action-{iteration}.csv"
        )
        actions_data = self.read_actions_log(actions_file_path, iteration)
        if not actions_data:
            logger.critical("No valid action data found.")
            self.spec_check_logger.log_spec_check(
                iteration, "No valid action data found.", "-", "-", "-", "-"
            )
            return

        agreement_results = ConsensusProperties.check_agreement_properties(ledgers_data)
        integrity_results = ConsensusProperties.check_integrity_properties(actions_data)
        validity_results = ConsensusProperties.check_validity_properties(
            ledgers_data, actions_data, [] # Placeholder for Byzantine nodes list
        )

        self.spec_check_logger.log_spec_check(
            iteration,
            agreement_results["all_ledger_goal_reached"],
            agreement_results["all_hashes_pass"],
            agreement_results["all_indexes_pass"],
            integrity_results["integrity"],
            validity_results["validity"]
        )

        logger.info(
            f"Specification check for iteration {iteration}: "
            f"reached goal ledger: {agreement_results['all_ledger_goal_reached']}, "
            f"same ledger hashes: {agreement_results['all_hashes_pass']}, "
            f"same ledger indexes: {agreement_results['all_indexes_pass']}"
            f"integrity: {integrity_results['integrity']}"
            f"validity: {validity_results['validity']}"
        )

    def aggregate_spec_checks(self):
        """Aggregate the spec check results and write them to a final file."""
        spec_check_file_path = f"logs/{self.log_dir}/spec_check_log.csv"
        agg_spec_check_file_path = f"logs/{self.log_dir}/aggregated_spec_check_log.json"

        try:
            with open(spec_check_file_path, newline="") as file:
                reader = csv.DictReader(file)
                rows = list(reader)

            total_iterations = len(rows)
            correct_runs = sum(
                1
                for row in rows
                if row["reached_goal_ledger"] == "True"
                and row["same_ledger_hashes"] == "True"
                and row["same_ledger_indexes"] == "True"
                and row["integrity"] == "True"
                and row["validity"] == "True"
            )
            timeout_before_startup = sum(
                1
                for row in rows
                if row["reached_goal_ledger"] == "timeout reached before startup"
            )
            errors = sum(1 for row in rows if "error" in row["reached_goal_ledger"])
            failed_termination = sum(
                1 for row in rows if row["reached_goal_ledger"] == "False"
            )
            failed_agreement = sum(
                1
                for row in rows
                if row["same_ledger_hashes"] == "False"
                or row["same_ledger_indexes"] == "False"
            )
            failed_integrity = sum(
                1 for row in rows if row["integrity"] == "False"
            )
            failed_validity = sum(
                1 for row in rows if row["validity"] == "False"
            )
            failed_termination_iterations = [
                row["iteration"]
                for row in rows
                if row["reached_goal_ledger"] == "False"
            ]
            failed_agreement_iterations = [
                row["iteration"]
                for row in rows
                if row["same_ledger_hashes"] == "False"
                or row["same_ledger_indexes"] == "False"
            ]
            failed_integrity_iterations = [
                row["iteration"]
                for row in rows
                if row["integrity"] == "False"
            ]
            failed_validity_iterations = [
                row["iteration"]
                for row in rows
                if row["validity"] == "False"
            ]

            aggregated_data = {
                "total_iterations": total_iterations,
                "correct_runs": correct_runs,
                "timeout_before_startup": timeout_before_startup,
                "errors": errors,
                "failed_termination": failed_termination,
                "failed_agreement": failed_agreement,
                "failed_integrity": failed_integrity,
                "failed_validity": failed_validity,
                "failed_termination_iterations": failed_termination_iterations,
                "failed_agreement_iterations": failed_agreement_iterations,
                "failed_integrity_iterations": failed_integrity_iterations,
                "failed_validity_iterations": failed_validity_iterations,
            }

            logger.info(f"Aggregated spec check results: {aggregated_data}")

            with open(agg_spec_check_file_path, mode="w") as file:
                json.dump(aggregated_data, file, indent=4)
        except Exception as e:
            logger.error(f"Error aggregating spec checks: {e}")
