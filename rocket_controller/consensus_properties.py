from collections import defaultdict
from typing import Dict, List, Set

class ConsensusProperties:

    @staticmethod
    def extract_propose_sets(actions_data: Dict[int, List[dict]], byzantine_nodes: Set[int]) -> Dict[int, Set[str]]:
        propose_sets = defaultdict(set)

        for node_id, actions in actions_data.items():
            if node_id in byzantine_nodes:
                continue  # Ignore proposal messages from Byzantine nodes
            for action in actions:
                if action["message_type"] == "TMProposeSet" and "ledger_seq" in action["protobuf_obj"]:
                    seq = action["protobuf_obj"]["ledger_seq"]
                    tx_hash = action["protobuf_obj"]["currentTxHash"]
                    propose_sets[seq].add(tx_hash)

        return propose_sets

    @staticmethod
    def check_validity_properties(ledgers_data: Dict[int, List[dict]], actions_data: Dict[int, List[dict]], byzantine_nodes: Set[int]) -> dict[str, bool | str]:
        """
        Check whether validated transaction sets of each node are actually in the proposed transaction sets.
        """
        validity_satisfied = True
        propose_sets = ConsensusProperties.extract_propose_sets(actions_data, byzantine_nodes)

        for seq, ledger_entries in ledgers_data.items():
            ledger_hashes = {
                entry["ledger_hash"]
                for entry in ledger_entries
                if entry["node_id"] not in byzantine_nodes  # Ignore consensus messages from Byzantine nodes
            }

            proposed_tx_sets = propose_sets.get(seq, set())

            # for each transaction validated by ledger (ledger_hash) check if its in proposed_tx_sets (which is also a hash not a set of transactions)

        return {
            "validity": validity_satisfied,
        }

    @staticmethod
    def check_integrity_properties(actions_data: dict[int, list[dict]]) -> dict[str, bool | str]:
        """
        Check whether consensus messages have the same ledger hashes for the same sequence number.
        """
        agreement_satisfied = True
        seqs = set()
        for actions in actions_data.values():
            for action in actions:
                if action["message_type"] == "TMStatusChange" and hasattr(action["protobuf_obj"], "ledgerSeq"):
                    seqs.add(action["protobuf_obj"]["ledgerSeq"])

        for seq in seqs:
            ledger_hashes = [
                action["protobuf_obj"]["ledgerHash"]
                for actions in actions_data.values()
                for action in actions
                if action["message_type"] == "TMStatusChange"
                and "ledgerHash" in action["protobuf_obj"]
                and action["protobuf_obj"]["ledgerSeq"] == seq
            ]

            if len(set(ledger_hashes)) > 1:
                agreement_satisfied = False

        return {
            "integrity": agreement_satisfied,
        }
    
    @staticmethod
    def check_agreement_properties(ledgers_data: dict[int, list[dict]]) -> dict[str, bool | str]:
        sorted_keys = sorted(ledgers_data.keys())
        # logger.debug(f"Found data for ledger sequences: {sorted_keys}")
        max_seq = sorted_keys[-1]
        min_seq = sorted_keys[0]

        all_hashes_pass = True
        all_indexes_pass = True
        all_ledger_goal_reached = (
            len(ledgers_data[max_seq]) == len(ledgers_data[min_seq])
            and max_seq == ledgers_data[min_seq][0]["goal_ledger_seq"]
        )
        for _, records in ledgers_data.items():
            ledger_hashes_same = all(
                x["ledger_hash"] == records[0]["ledger_hash"] for x in records
            )
            ledger_indexes_same = all(
                x["ledger_index"] == records[0]["ledger_index"] for x in records
            )
            all_hashes_pass &= ledger_hashes_same
            all_indexes_pass &= ledger_indexes_same
        return {
            "all_ledger_goal_reached": all_ledger_goal_reached,
            "all_hashes_pass": all_hashes_pass,
            "all_indexes_pass": all_indexes_pass,
        }