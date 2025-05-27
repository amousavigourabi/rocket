"""This file contains a class to run and manage evolutionary based testing approaches."""
import csv
import glob
import shutil
from asyncio import as_completed
from concurrent.futures.thread import ThreadPoolExecutor
from curses.ascii import isxdigit
from datetime import datetime
import random
import subprocess
import sys
from pathlib import Path
from time import sleep

import yaml
from typing import Tuple

from operators import SBX, GaussianMutation
from rocket_controller.helper import format_datetime



def process_results(log_dir):
    result_files = glob.glob(f"logs/{log_dir}/**/result-*.csv")
    validation_times = []

    for result_file in result_files:
        with open(result_file, 'r') as f:
            csv_reader = csv.DictReader(f)
            for row in csv_reader:
                if row['ledger_seq'] != '2':
                    validation_times.append(float(row['time_to_validation']))
    return sum(validation_times) / len(validation_times) if validation_times else 0




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

        self.image = "rocket-image"
        self.shared_path = "/home/bwassenaar/Projects/research_project"
        self.main_hostname_prefix = "BW_Baseline"
        self.workers = 5 # workers refers to the amount of rocket controllers started at the same time. This means you will need 10 free threads per worker.
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
        crossover = SBX()
        mutate = GaussianMutation(self.encoding_min, self.encoding_max)

        elite = population[0:5]

        crossover_population = crossover.crossover(population[:-5])
        mutated_population = mutate.mutate(crossover_population)
    
        return elite + mutated_population


    def run_rocket(self, encoding: list[int], generation: int, testcase: int, retry: int = 0):
        """
        Run rocket with set configurations.

        Args:
            retry: Number of retries left.
            log_dir: Directory where logs should be stored.
            encoding: encoding of numbers to be used by evolutionary strategy
        """

        if len(encoding) != self.encoding_length:
            raise ValueError(f"Encoding should be of length {self.encoding_length}, but got {len(encoding)}")
        print(f"Running rocket with encoding {encoding}")
        hostname_prefix = f"{self.main_hostname_prefix}_G{generation}T{testcase}R{retry}"

        log_dir = f"{self.shared_path}/logs/{self.main_hostname_prefix}/{hostname_prefix}"
        Path.mkdir(Path(log_dir), parents=True, exist_ok=True)
        with open(f"{log_dir}/run_info.txt", mode="a") as f:
            f.write(f"Seed: {self.seed}")
            f.write(f"\nEncoding: {encoding}")

        name = f"{hostname_prefix}_controller"
        docker_command = ["docker","run","--rm","--name", name,"--network", "rocket_net","-v","/var/run/docker.sock:/var/run/docker.sock","-v",f"{self.shared_path}:{self.shared_path}", "-e", f"ROCKET_NETWORK_MOUNT={self.shared_path}", self.image]
        python_args = [self.strategy, "--nodes", str(self.nodes), "--encoding", str(encoding),"--hostname_prefix",hostname_prefix,"--log_dir",log_dir ]
        command = docker_command + python_args

        process = subprocess.Popen(
            command,
            text=True
        )
        return_code = process.wait()
        if return_code != 0:
            if retry < 3:
                retry += 1
                print(f"Rocket failed on attempt {retry}. Retrying...")
                sleep(5)
                return self.run_rocket(encoding, generation, testcase, retry)
            raise Exception(f"Rocket failed after {retry} retries. THIS IS NOT GOOD!")

        average_validation_time = process_results(log_dir)
        with open(f"logs/{hostname_prefix}/run_info.txt", mode="a") as f:
            f.write(f"\nAverage validation time: {average_validation_time} seconds")
        print(f"Average validation time: {average_validation_time} seconds")
        return average_validation_time, encoding

    def run_evolution_round(self, generation: int, population: list[list[int]]):
        results = []
        print(f"Running evolution with {len(population)} test cases.")

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            future_to_test = {
                executor.submit(self.run_rocket, test_case, generation, idx + 1, 0): idx
                for idx, test_case in enumerate(population)
            }
            for future in as_completed(future_to_test):
                result = future.result()
                results.append(result)

        return results

    def main(self):
        start_time = datetime.now()
        population = [self.initial_population() for _ in range(self.population_size)]
        for idx in range(self.generations):
            print(f"Generation {idx+1}")
            results = self.run_evolution_round(idx+1, population)

            new_population = [] #elitism, add x best individuals

            while len(new_population) < len(population):
                selected = self.selection(results) # 2 paremts
                children = self.reproduction(selected)
                new_population.append(children)

            population = new_population
        return


if __name__ == "__main__":
    manager = EvoTestManager()
    manager.main()