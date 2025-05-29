"""This module contains functionality to easily interact with the network packet interceptor subprocess."""
import subprocess
import traceback
from subprocess import PIPE, Popen, TimeoutExpired
from sys import platform
from threading import Thread

import docker
from docker import DockerClient
from loguru import logger


def cleanup_docker_containers(hostname_prefix: str):
    try:
        client = docker.from_env()

        all_containers = client.containers.list()
        containers = [c for c in all_containers if c.name.startswith(f"{hostname_prefix}_validator")]
        for container in containers:
            try:
                container.stop()
            except Exception as e:
                print(f"Failed to stop container {container.name}. Error: {e}")
    except Exception as e:
        print(f"Error cleaning up docker containers: {e}")


class InterceptorManager:
    """Class for interacting with the network packet interceptor subprocess."""

    def __init__(self):
        """Initialize the InterceptorManager, with None for the process variable."""
        self.process: Popen | None = None

    @staticmethod
    def __check_output(proc: Popen):
        """Log the stdout and stderr of the subprocess."""
        stdout, stderr = proc.communicate()
        if stdout:
            logger.debug(f"\n{stdout}")
        if stderr:
            logger.debug(f"\n{stderr}")


    def start_new(self):
        """Starts the rocket-interceptor subprocess, and spawns a thread checking for output."""
        file = (
            "rocket-interceptor"
            if platform != "win32"
            else "/rocket_interceptor/rocket-interceptor.exe"
        )
        logger.info("Starting interceptor")
        try:
            self.process = Popen(
                [f"./{file}"],
                cwd="./rocket_interceptor",
                stdin=PIPE,
                stdout=PIPE,
                stderr=PIPE,
                text=True,
            )
        except FileNotFoundError as exc:
            logger.error(
                "Could not find the rocket-interceptor executable. Did you build the interceptor?"
            )
            traceback.print_exception(exc)
            exit(2)

        t = Thread(target=self.__check_output, args=[self.process])
        t.start()

    def restart(self):
        """Stops and starts the rocket-interceptor subprocess."""
        self.stop()
        self.start_new()

    def stop(self):
        """Stops the rocket-interceptor subprocess."""
        # Check if this is the end of an active run
        if self.process:
            logger.info("Stopping interceptor")
            self.process.terminate()
            try:
                self.process.wait(timeout=5.0)
            except TimeoutExpired:
                self.process.kill()
