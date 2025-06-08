"""This file contains a class to run and manage byzzfuzz based testing approaches."""
import csv
import glob
import json
import shutil
import signal
import time
from concurrent.futures import as_completed
from concurrent.futures.thread import ThreadPoolExecutor
from curses.ascii import isxdigit
from datetime import datetime
import random
import subprocess
import sys
import copy
from pathlib import Path
from time import sleep
from deap import base, creator, tools

import docker
import yaml
from typing import Tuple

from docker.errors import NotFound, APIError

def process_results(log_dir):
    result_files = glob.glob(f"{log_dir}/**/result-*.csv")
    validation_times = []

    for result_file in result_files:
        with open(result_file, 'r') as f:
            csv_reader = csv.DictReader(f)
            for row in csv_reader:
                if row['ledger_seq'] != '2':
                    validation_times.append(float(row['time_to_validation']))

    agg_spec_check_files = glob.glob(f"{log_dir}/aggregated_spec_check_log.json")
    total_failures = 0

    if agg_spec_check_files:
        agg_file = agg_spec_check_files[0]
        with open(agg_file, 'r') as f:
            data = json.load(f)
            failed_termination = data.get('failed_termination', 0)
            failed_agreement = data.get('failed_agreement', 0)
            print("Log dir: {}".format(log_dir))
            print("Termination faults: ", failed_termination)
            print("Agreement faults: ", failed_agreement)
            total_failures = failed_termination + failed_agreement

    return ((sum(validation_times) / len(validation_times)) if validation_times else 0), total_failures

def cleanup_docker(hostname_prefix: str, max_attempts: int = 8):
    attempt = 0

    while attempt < max_attempts:
        try:
            client = docker.from_env()
            all_containers = client.containers.list(all=True)
            containers = [c for c in all_containers if c.name.startswith(f"{hostname_prefix}_validator")]

            for container in containers:
                try:
                    container.remove(force=True)
                    print(f"Removed container: {container.name}")
                except NotFound:
                    print(f"Container {container.name} already removed.")
                except APIError as e:
                    print(f"APIError removing {container.name}: {e}")
                except Exception as e:
                    print(f"Unexpected error removing {container.name}: {e}")
            return  # Success, break out of loop

        except Exception as e:
            print(f"Error accessing Docker: {e}")
            attempt += 1
            if attempt < max_attempts:
                print(f"Retrying in 2 seconds... (Attempt {attempt}/{max_attempts})")
                time.sleep(2)
            else:
                print("Max retry attempts reached. Exiting.")

class ByzzFuzzTestManager:
    """Manager for byzzfuzz based testing approaches."""

    def __init__(self, config_path='byzzfuzz_test_manager.yaml'): 
        """
        Initializes ByzzFuzzTestManager.
        
        Args:
            config_path: path to the config file.
        """
        config_path = Path(config_path)
        if not config_path.exists():
            raise ValueError(f"config file {config_path} does not exist")
        with open(config_path, 'r') as f:
            self._config = yaml.safe_load(f)

        # general section of the config file
        strategy = self._config['general']['strategy']
        if not strategy in ['ByzzFuzzBaseline', 'ByzzFuzzStrategy']:
            raise ValueError(f"strategy should be in {{'ByzzFuzzBaseline', 'ByzzFuzzStrategy'}}, but got {strategy}")
        self.strategy = strategy

        self.seed = self._config['general'].get('seed', None)
        if self.seed is None:
            self.seed = random.randint(0, 1000000)
            print(f"Seed not specified, using {self.seed}")
        random.seed(self.seed)

        # strategy section of the config file
        if self.strategy == "ByzzFuzzStrategy":
            byzzfuzz = self._config['byzzfuzz']
            self.rounds = byzzfuzz['rounds']
            self.min_network_faults = byzzfuzz['min_network_faults']
            self.max_network_faults = byzzfuzz['max_network_faults']
            self.min_process_faults = byzzfuzz['min_process_faults']
            self.max_process_faults = byzzfuzz['max_process_faults']
            self.small_scope = byzzfuzz['small_scope']
        elif self.strategy == "ByzzFuzzBaseline":
            baseline = self._config['baseline']
            self.drop_probability = baseline['drop_probability']
            self.corrupt_probability = baseline['corrupt_probability']

        self.image = "rocket-image-aiste"
        self.xrpl_image = "ghcr.io/amousavigourabi/docker-rippled/seeded-2.4.0-lower-agreement-threshold:latest"
        # self.output_path = "/data/home/bwassenaar/shared_rocket"
        self.main_hostname_prefix = "byzzfuzz_UNL100_seeded_"
        self.shared_volume = f"{self.main_hostname_prefix}_data"
        self.workers = 5  # workers refers to the amount of rocket controllers started at the same time. This means you will need 10 free threads per worker.
        # Do not use more than 5 on the research server!

    def run_rocket(self, log_dir: str, network_faults: int = 0, process_faults: int = 0, retry: int = 0):
        """
        Run rocket with set configurations.

        Args:
            retry: Number of retries left.
            log_dir: Directory where logs should be stored.
        """
        if self.strategy == "ByzzFuzzStrategy":
            hostname_prefix = f"{self.main_hostname_prefix}_network-faults-{network_faults}_process-faults-{process_faults}_small-scope-{self.small_scope}_R{retry}"
            print(f"Running rocket with network faults {network_faults}, process faults {process_faults}, small scope {self.small_scope}, retry {retry}")
        else:
            hostname_prefix = f"{self.main_hostname_prefix}_drop-{self.drop_probability}_corrupt-{self.corrupt_probability}_R{retry}"
            print(f"Running rocket with drop probability {self.drop_probability}, corrupt probability {self.corrupt_probability}, retry {retry}")

        log_dir = f"/shared/logs/{self.main_hostname_prefix}/{hostname_prefix}"
        Path.mkdir(Path(log_dir), parents=True, exist_ok=True)
        with open(f"{log_dir}/run_info.txt", mode="a") as f:
            f.write(f"Seed: {self.seed}")
            f.write(f"\nStrategy: {self.strategy}")
            if self.strategy == "ByzzFuzzStrategy":
                f.write(f"\nRounds: {self.rounds}")
                f.write(f"\nNetwork faults: {network_faults}")
                f.write(f"\nProcess faults: {process_faults}")
                f.write(f"\nSmall scope: {self.small_scope}")
            elif self.strategy == "ByzzFuzzBaseline":
                f.write(f"\nDrop probability: {self.drop_probability}")
                f.write(f"\nCorrupt probability: {self.corrupt_probability}")
        
        name = f"{hostname_prefix}_controller"
        if self.strategy == "ByzzFuzzStrategy":
            python_args = ["-m", "rocket_controller", self.strategy, "--rounds", str(self.rounds), "--network_faults", str(network_faults),
            "--process_faults", str(process_faults), "--small_scope", str(self.small_scope),
            "--hostname_prefix", hostname_prefix, "--log_dir", log_dir]
        elif self.strategy == "ByzzFuzzBaseline":
            python_args = ["-m", "rocket_controller", self.strategy, "--drop_probability", str(self.drop_probability),
            "--corrupt_probability", str(self.corrupt_probability), "--hostname_prefix", hostname_prefix, "--log_dir", log_dir]
        client = docker.from_env()
        try:
            container = client.containers.run(
                image=self.image,
                name=name,
                command=python_args,
                network="rocket_net",
                auto_remove=False,
                environment={
                    "ROCKET_NETWORK_MOUNT": self.shared_volume,
                    "ROCKET_XRPLD_DOCKER_CONTAINER": self.xrpl_image
                },
                volumes={
                    "/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "rw"},
                    self.shared_volume: {"bind": "/shared", "mode": "rw"},
                },
                detach=True,
            )

            with open(f"{log_dir}/stdout.txt", mode="w") as out_file:
                result = container.wait(timeout=10*60)
                logs = container.logs(stdout=True, stderr=True, timestamps=True)
                out_file.write(logs.decode(errors="ignore"))
            exit_code = result.get("StatusCode", -1)
        except Exception as e:
            if retry < 2:
                retry += 1
                print(f"Rocket failed on attempt {retry}. Retrying...")
                cleanup_docker(hostname_prefix)
                sleep(5)
                return self.run_rocket(log_dir, network_faults, process_faults, retry)
            raise Exception(f"Rocket timed out after {retry} retries. THIS IS NOT GOOD!")

        if exit_code != 0:
            if retry < 2:
                retry += 1
                print(f"Rocket failed on attempt {retry}. Retrying...")
                cleanup_docker(hostname_prefix)
                sleep(5)
                return self.run_rocket(log_dir, network_faults, process_faults, retry)
            raise Exception(f"Rocket failed after {retry} retries. THIS IS NOT GOOD!")

        average_validation_time, violations = process_results(log_dir)
        with open(f"{log_dir}/run_info.txt", mode="a") as f:
            f.write(f"\nAverage validation time: {average_validation_time} seconds")
            f.write(f"\nTotal violations: {violations}")
        print(f"Average validation time: {average_validation_time} seconds")
        print(f"Total violations: {violations}")
        cleanup_docker(hostname_prefix)
        return average_validation_time, violations

    def main(self):
        start_time = datetime.now()
        shutil.copytree("./rocket_interceptor/network", f"/shared/network", dirs_exist_ok=True)

        population = []
        if self.strategy == "ByzzFuzzStrategy":
            for network_faults in range(self.min_network_faults, self.max_network_faults + 1):
                for process_faults in range(self.min_process_faults, self.max_process_faults + 1):
                    population.append({"network_faults": network_faults, "process_faults": process_faults})
        elif self.strategy == "ByzzFuzzBaseline":
            population.append({"drop_probability": self.drop_probability, "corrupt_probability": self.corrupt_probability})
        
        results = []
        print(f"Running byzzfuzz with {len(population)} test cases.")

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {}

            for idx, test_case in enumerate(population):
                network_faults = test_case.get("network_faults", 0)
                process_faults = test_case.get("process_faults", 0)
                future = executor.submit(self.run_rocket, f"testcase-{idx + 1}", network_faults, process_faults)
                futures[future] = test_case

            for future in as_completed(futures.keys()):
                result = (future.result(), futures[future])
                results.append(result)

        return

if __name__ == "__main__":
    manager = ByzzFuzzTestManager()
    manager.main()