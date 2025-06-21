"""This file contains a class to run and manage evolutionary based testing approaches."""
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
    action_files = glob.glob(f"{log_dir}/**/action-*.csv")
    propose_count = 0

    for action_file in action_files:
        with open(action_file, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('message_type') == 'TMProposeSet':
                    propose_count += 1

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

    time_f = (sum(validation_times) / len(validation_times)) if validation_times else 0

    return time_f, propose_count, total_failures


def cleanup_docker(hostname_prefix: str, max_attempts: int = 14):
    attempt = 0

    while attempt < max_attempts:
        try:
            client = docker.from_env()
            all_containers = client.containers.list(all=True)
            containers = [c for c in all_containers if (c.name.startswith(f"{hostname_prefix}_controller") or c.name.startswith(f"{hostname_prefix}_validator"))]

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


class EvoTestManager:
    """Manager for evolutionary based testing approaches."""

    def __init__(self, config_path='evo_test_manager.yaml'):
        """
        Initializes an EvoTestManager.

        Args:
            config_path: path to the config file.
        """
        config_path = Path(config_path)
        if not config_path.exists():
            raise ValueError(f"config file {config_path} does not exist")
        with open(config_path, 'r') as f:
            self._config = yaml.safe_load(f)

        # General section of the config file
        nodes = self._config['general']['nodes']
        if nodes < 2:
            raise ValueError(f"nodes should be at least 2, but got {nodes}")
        self.nodes = nodes

        strategy = self._config['general']['strategy']
        if not strategy in ['EvoDelayStrategy', 'EvoPriorityStrategy']:
            raise ValueError(f"strategy should be in {{'EvoDelayStrategy', 'EvoPriorityStrategy'}}, but got {strategy}")
        self.strategy = strategy

        self.seed = self._config['general'].get('seed', None)
        if self.seed is None:
            self.seed = random.randint(0, 1000000)
            print(f"seed not specified, using {self.seed}")
        random.seed(self.seed)

        # Evolution section of the config file
        population_size = self._config['evolution']['population_size']
        if population_size < 2:
            raise ValueError(f"population_size should be at least 2, but got {population_size}")
        self.population_size = population_size

        generations = self._config['evolution']['generations']
        if generations < 1:
            raise ValueError(f"generations should be at least 1, but got {generations}")
        self.generations = generations

        # Encoding section of the config file
        encoding = self._config['encoding']
        self.encoding_min = encoding['min_value']
        self.encoding_max = encoding['max_value']
        self.encoding_length = 7 * self.nodes * (self.nodes - 1)

        self.image = "rocket-image-atour"
        self.xrpl_image = "ghcr.io/amousavigourabi/docker-rippled/seeded-2.4.0-fully-lowered-threshold:latest"
        # self.output_path = "/data/home/bwassenaar/shared_rocket"
        self.main_hostname_prefix = "AMG_TournamentDCD"
        self.shared_volume = f"{self.main_hostname_prefix}_data"
        self.workers = 5  # workers refers to the amount of rocket controllers started at the same time. This means you will need 10 free threads per worker.
        # Do not use more than 5 on the research server!

    def initial_population(self):
        return [random.randint(self.encoding_min, self.encoding_max) for _ in range(self.encoding_length)]

    def selection(self, results: list[Tuple[list[int], list[int]]]):
        # TODO first list[int] is a placeholder, should be the type of results from run_rocket
        # TODO run fitness function on the results, then determine which ones are fit
        # Temporarily passthrough all populations
        populations = []
        for result, population in results:
            populations.append(population)
        return populations

    def reproduction(self, population: list[list[int]]):
        """
        Perform reproduction using Simulated Binary Crossover and Gaussian Mutation.

        Args:
            population: List of populations to perform reproduction on

        Returns:
            List of new populations after crossover and mutation
        """
        # crossover = SBX()
        # mutate = GaussianMutation(self.encoding_min, self.encoding_max)
        #
        # elite = population[0:5]
        #
        # crossover_population = crossover.crossover(population[:-5])
        # mutated_population = mutate.mutate(crossover_population)

        new_population: list[list[int]] = []
        for idx, individual in enumerate(population):
            new_population.append(self.initial_population())
        return new_population
        # return elite + mutated_population

    def run_rocket(self, encoding: list[int], generation: int, testcase: int, retry: int = 0):
        """
        Run rocket with set configurations.

        Args:
            retry: Number of retries left.
            log_dir: Directory where logs should be stored.
            encoding: encoding of numbers to be used by evolutionary strategy
        """

        if len(encoding) != self.encoding_length:
            raise ValueError(
                f"Encoding should be of length {self.encoding_length}, but got {len(encoding)}\nEncoding: {encoding}")
        print(f"Running rocket with encoding {encoding}")
        hostname_prefix = f"{self.main_hostname_prefix}_G{generation}T{testcase}R{retry}"

        log_dir = f"/shared/logs/{self.main_hostname_prefix}/{hostname_prefix}"
        Path.mkdir(Path(log_dir), parents=True, exist_ok=True)
        with open(f"{log_dir}/run_info.txt", mode="a") as f:
            f.write(f"Seed: {self.seed}")
            f.write(f"\nEncoding: {encoding}")

        name = f"{hostname_prefix}_controller"

        python_args = ["-m", "rocket_controller", self.strategy, "--nodes", str(self.nodes), "--encoding",
                       str(encoding), "--hostname_prefix", hostname_prefix, "--log_dir", log_dir]

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
                result = container.wait(timeout=20*60)
                logs = container.logs(stdout=True, stderr=True, timestamps=True)
                out_file.write(logs.decode(errors="ignore"))
            exit_code = result.get("StatusCode", -1)
        except Exception as e:
            print("Exception", e)
            if retry < 6:
                retry += 1
                print(f"Rocket failed on attempt {retry}. Retrying...")
                cleanup_docker(hostname_prefix)
                sleep(5)
                return self.run_rocket(encoding, generation, testcase, retry)
            raise Exception(f"Rocket timed out after {retry} retries. THIS IS NOT GOOD!")

        if exit_code != 0:
            print(f"Rocket exited with status {exit_code}")
            if retry < 6:
                retry += 1
                print(f"Rocket failed on attempt {retry}. Retrying...")
                cleanup_docker(hostname_prefix)
                sleep(5)
                return self.run_rocket(encoding, generation, testcase, retry)
            raise Exception(f"Rocket failed after {retry} retries. THIS IS NOT GOOD!")

        average_validation_time, proposals, violations = process_results(log_dir)
        with open(f"{log_dir}/run_info.txt", mode="a") as f:
            f.write(f"\nAverage validation time: {average_validation_time} seconds")
            f.write(f"\nProposal count: {proposals}")
            f.write(f"\nTotal violations: {violations}")
        print(f"Average validation time: {average_validation_time} seconds")
        print(f"Proposal count: {proposals}")
        print(f"Total violations: {violations}")
        cleanup_docker(hostname_prefix)
        return average_validation_time, proposals, violations

    def run_evolution_round(self, generation: int, population: list[list[int]]):
        results = []
        print(f"Running evolution with {len(population)} test cases.")

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {}
            for idx, test_case in enumerate(population):
                future = executor.submit(self.run_rocket, test_case, generation, idx + 1, 0)
                futures[future] = test_case

            for future in as_completed(futures.keys()):
                result = (future.result(), futures[future])
                results.append(result)

        return results

    def main(self):
        start_time = datetime.now()
        shutil.copytree("./rocket_interceptor/network", f"/shared/network")

        creator.create("FitnessMulti", base.Fitness, weights=(1.0, 1.0))  # Maximize both
        creator.create("Individual", list, fitness=creator.FitnessMulti)

        population = [self.initial_population() for _ in range(self.population_size)]
        prev_results = self.run_evolution_round(1, population)
        population = []
        for (time, proposals, _), encoding in prev_results:
            ind = creator.Individual(encoding)
            ind.fitness.values = (time, proposals)
            population.append(ind)

        for idx in range(1, self.generations):
            print(f"Generation {idx + 1}")

            tools.sortNondominated(population, len(population))
            tools.emo.assignCrowdingDist(population)
            offspring = [self.initial_population() for _ in range(self.population_size)]

            while len(offspring) < self.population_size:

                # Select two parents using elitism
                parents = tools.selTournamentDCD(population, 2, 8)
                parent1, parent2 = parents[0], parents[1]

                # Clone parents to create children
                child1, child2 = copy.deepcopy(parent1), copy.deepcopy(parent2)

                # sbx_with_prob(child1, child2, eta=3.0)

                tools.cxSimulatedBinaryBounded(child1, child2, eta=3.0, low=0, up=4000)
                # tools.cxBlend(child1, child2, alpha=0.7)

                # Apply Gaussian mutation with probability 0.1 per child
                tools.mutGaussian(child1, mu=0, sigma=40, indpb=(1.0 / 42.0))
                tools.mutGaussian(child2, mu=0, sigma=40, indpb=(1.0 / 42.0))

                # tools.mutPolynomialBounded(child1, eta=20.0, low=0, up=4000, indpb=(1.0 / 42.0))
                # tools.mutPolynomialBounded(child2, eta=20.0, low=0, up=4000, indpb=(1.0 / 42.0))

                # custom_gaussian_mutation(child1, 0, 4000)
                # custom_gaussian_mutation(child2, 0, 4000)

                # Invalidate fitness values of offspring
                del child1.fitness.values
                del child2.fitness.values

                # Round each gene in the child and clamp
                child1[:] = [min(4000, max(0, round(gene))) for gene in child1]
                child2[:] = [min(4000, max(0, round(gene))) for gene in child2]

                offspring.append(child1)
                if len(offspring) < self.population_size:
                    offspring.append(child2)

            results = self.run_evolution_round(idx + 1, list(offspring))   # results is list[((time, violations), encoding)]

            offspring = []
            for (time, proposals, _), encoding in results:
                ind = creator.Individual(encoding)
                ind.fitness.values = (time, proposals)
                offspring.append(ind)

            everything = population + offspring

            tools.sortNondominated(everything, len(everything))
            tools.emo.assignCrowdingDist(everything)

            # Select new generation using NSGA-II
            population = tools.selTournamentDCD(everything, k=self.population_size)

        return

if __name__ == "__main__":
    manager = EvoTestManager()
    manager.main()


